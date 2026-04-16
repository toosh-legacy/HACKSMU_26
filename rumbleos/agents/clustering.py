import multiprocessing as mp
import numpy as np
from pathlib import Path
import json
from agents.runtime import configure_runtime
from agents.serialization import tabular_result

configure_runtime()

class ClusteringAgent(mp.Process):
    """
    Stage 7: Pattern clustering + Tribe + Claude API.

    Triggered ONCE when all results are collected (receives list via queue).
    Runs UMAP + K-means, builds Tribe similarity graph, calls Claude API.
    """
    def __init__(self, in_queue, output_dir, gemini_api_key=None):
        super().__init__(daemon=True)
        self.in_queue   = in_queue
        self.output_dir = Path(output_dir)
        self.api_key    = gemini_api_key
        self.context_fields = [
            "elephant_id",
            "age_class",
            "age",
            "sex",
            "location",
            "location_id",
            "camera_id",
            "recorder_id",
            "recording_device",
            "relationship",
            "relationship_group",
            "family_group",
            "clan",
            "breeding_context",
            "breeding_target",
            "call_type",
        ]

    @staticmethod
    def extract_features(r: dict) -> list:
        dur = r.get('end_time', 0) - r.get('start_time', 0)
        return [
            r.get('f0_hz', 0),
            dur,
            r.get('harmonics_present', 0),
            r.get('harmonic_completeness', 0),
            r.get('snr_after_db', 0),
            r.get('snr_improvement_db', 0),
            1.0 if r.get('multi_elephant') else 0.0,
            r.get('f0_b', 0),
        ]

    def _context_columns(self, df):
        return [col for col in self.context_fields if col in df.columns]

    @staticmethod
    def _context_payload(row, context_cols):
        payload = {}
        for col in context_cols:
            value = row.get(col)
            if value is None:
                continue
            if isinstance(value, float) and np.isnan(value):
                continue
            payload[col] = value.item() if isinstance(value, np.generic) else value
        return payload

    @staticmethod
    def _metadata_affinity(context_a: dict, context_b: dict) -> float:
        weighted_fields = {
            "elephant_id": 4.0,
            "family_group": 3.0,
            "relationship_group": 3.0,
            "clan": 3.0,
            "sex": 2.0,
            "age_class": 2.0,
            "location": 2.0,
            "location_id": 2.0,
            "breeding_context": 2.0,
            "breeding_target": 2.0,
            "call_type": 1.0,
            "camera_id": 1.0,
            "recorder_id": 1.0,
            "recording_device": 1.0,
        }
        overlap = 0.0
        max_score = 0.0
        for field, weight in weighted_fields.items():
            a = context_a.get(field)
            b = context_b.get(field)
            if a is None or b is None:
                continue
            max_score += weight
            if str(a) == str(b):
                overlap += weight
        return overlap / max_score if max_score else 0.0

    def _build_knowledge_base(self, valid_df, call_ids, labels, coords_2d, acoustic_sim, context_cols):
        records = []
        for idx, row in valid_df.iterrows():
            context = self._context_payload(row, context_cols)
            records.append({
                "call_id": row["call_id"],
                "recording_id": row.get("recording_id"),
                "cluster": int(labels[idx]),
                "umap_x": round(float(coords_2d[idx, 0]), 3),
                "umap_y": round(float(coords_2d[idx, 1]), 3),
                "comparison_image": row.get("comparison_image"),
                "f0_hz": row.get("f0_hz"),
                "snr_improvement_db": row.get("snr_improvement_db"),
                "multi_elephant": bool(row.get("multi_elephant", False)),
                "context": context,
            })

        links = []
        for i in range(len(call_ids)):
            context_a = records[i]["context"]
            for j in range(i + 1, len(call_ids)):
                context_b = records[j]["context"]
                meta_sim = self._metadata_affinity(context_a, context_b)
                combined = 0.7 * float(acoustic_sim[i, j]) + 0.3 * meta_sim
                if combined < 0.72 and meta_sim < 0.8:
                    continue
                reasons = []
                if acoustic_sim[i, j] > 0.80:
                    reasons.append("acoustic_similarity")
                for field in context_cols:
                    if context_a.get(field) is not None and context_a.get(field) == context_b.get(field):
                        reasons.append(f"shared_{field}")
                links.append({
                    "source": call_ids[i],
                    "target": call_ids[j],
                    "acoustic_similarity": round(float(acoustic_sim[i, j]), 3),
                    "metadata_similarity": round(float(meta_sim), 3),
                    "combined_score": round(float(combined), 3),
                    "reasons": reasons,
                })

        cluster_profiles = {}
        for cluster_id in sorted(set(int(x) for x in labels)):
            members = [record for record in records if record["cluster"] == cluster_id]
            context_counts = {}
            for field in context_cols:
                values = [str(m["context"][field]) for m in members if field in m["context"]]
                if values:
                    uniques, counts = np.unique(values, return_counts=True)
                    context_counts[field] = dict(zip(uniques.tolist(), counts.tolist()))
            cluster_profiles[cluster_id] = {
                "count": len(members),
                "members": [m["call_id"] for m in members],
                "context_counts": context_counts,
            }

        knowledge_base = {
            "schema_version": 1,
            "description": "Context-aware elephant call knowledge base",
            "context_fields_used": context_cols,
            "calls": records,
            "association_links": links,
            "clusters": cluster_profiles,
        }
        (self.output_dir / "knowledge_base.json").write_text(json.dumps(knowledge_base, indent=2))

    def run(self):
        import pandas as pd
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        from sklearn.metrics.pairwise import cosine_similarity

        all_results = self.in_queue.get()
        valid = [r for r in all_results if r.get('valid')]
        print(f"[Clustering] {len(valid)} valid calls to cluster")

        if len(valid) < 5:
            print("[Clustering] not enough valid calls — skipping")
            return

        feat_matrix = np.array([self.extract_features(r) for r in valid])
        call_ids    = [r['call_id'] for r in valid]
        valid_df    = pd.DataFrame([tabular_result(r) for r in valid]).reset_index(drop=True)
        context_cols = self._context_columns(valid_df)

        acoustic_df = pd.DataFrame(feat_matrix, columns=[
            "f0_hz",
            "duration_s",
            "harmonics_present",
            "harmonic_completeness",
            "snr_after_db",
            "snr_improvement_db",
            "multi_elephant_flag",
            "f0_b",
        ])
        acoustic_X = StandardScaler().fit_transform(acoustic_df)
        X = acoustic_X
        if context_cols:
            context_df = valid_df[context_cols].fillna("unknown").astype(str)
            context_encoded = pd.get_dummies(context_df, prefix=context_cols)
            context_X = context_encoded.to_numpy(dtype=float)
            X = np.hstack([acoustic_X, context_X])

        # UMAP (falls back to PCA)
        try:
            import umap
            coords_2d = umap.UMAP(n_components=2, n_neighbors=10,
                                   min_dist=0.1, random_state=42).fit_transform(X)
        except ImportError:
            print("[Clustering] umap-learn not found, using PCA fallback")
            from sklearn.decomposition import PCA
            coords_2d = PCA(n_components=2).fit_transform(X)

        k      = min(7, max(2, len(valid) // 3))
        labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)

        # Annotate results
        for i, r in enumerate(valid):
            r['cluster'] = int(labels[i])
            r['umap_x']  = round(float(coords_2d[i, 0]), 3)
            r['umap_y']  = round(float(coords_2d[i, 1]), 3)
            if context_cols:
                r['context'] = self._context_payload(valid_df.iloc[i], context_cols)

        # Tribe graph (cosine similarity > 0.80)
        sim   = cosine_similarity(acoustic_X)
        edges = [
            {"source": call_ids[i], "target": call_ids[j],
             "weight": round(float(sim[i, j]), 3)}
            for i in range(len(call_ids))
            for j in range(i+1, len(call_ids))
            if sim[i, j] > 0.80
        ]

        # Cluster summaries
        summaries = {}
        for c in range(k):
            members = feat_matrix[labels == c]
            summaries[int(c)] = {
                "count":          int((labels == c).sum()),
                "mean_f0_hz":     round(float(members[:, 0].mean()), 1),
                "mean_dur_s":     round(float(members[:, 1].mean()), 2),
                "mean_harmonics": round(float(members[:, 2].mean()), 1),
                "mean_snr_db":    round(float(members[:, 4].mean()), 1),
                "call_ids":       [call_ids[i] for i, l in enumerate(labels) if l == c],
            }

        # Save outputs
        pd.DataFrame(edges).to_csv(self.output_dir / "tribe_edges.csv", index=False)
        (self.output_dir / "cluster_summaries.json").write_text(
            json.dumps(summaries, indent=2))
        # Save updated results with cluster info
        pd.DataFrame([tabular_result(r) for r in all_results]).to_csv(
            self.output_dir / "batch_results_clustered.csv", index=False)
        valid_df_out = pd.DataFrame([tabular_result(r) for r in valid])
        valid_df_out.to_csv(self.output_dir / "context_clusters.csv", index=False)
        self._build_knowledge_base(valid_df_out, call_ids, labels, coords_2d, sim, context_cols)

        print(f"[Clustering] {k} clusters | {len(edges)} Tribe edges")
        for c, s in summaries.items():
            print(f"  Cluster {c}: {s['count']} calls | "
                  f"F0={s['mean_f0_hz']}Hz | dur={s['mean_dur_s']}s")

        # Claude API hypotheses (optional)
        if self.api_key:
            self._generate_hypotheses(summaries)

    def _generate_hypotheses(self, summaries: dict):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            total = sum(v['count'] for v in summaries.values())
            prompt = (
                f"You are an expert in elephant bioacoustics and animal communication.\n\n"
                f"I clustered {total} elephant rumble calls into "
                f"{len(summaries)} acoustic groups:\n\n" +
                "\n".join(
                    f"Cluster {c}: {v['count']} calls | "
                    f"F0={v['mean_f0_hz']}Hz | duration={v['mean_dur_s']}s | "
                    f"harmonics={v['mean_harmonics']} | SNR={v['mean_snr_db']}dB"
                    for c, v in summaries.items()
                ) +
                "\n\nFor each cluster:\n"
                "1. What behavioral context might these calls represent? "
                "(greeting, alarm, coordination, contact call, play, etc.)\n"
                "2. Which clusters likely come from the same individual elephant? "
                "(similar F0 = similar body size)\n"
                "3. What are the 3 most important hypotheses to test?\n"
                "Be specific and cite acoustic properties in your reasoning."
            )
            resp = model.generate_content(prompt)
            (self.output_dir / "ai_hypotheses.txt").write_text(resp.text)
            print("[Clustering] Gemini hypotheses saved to ai_hypotheses.txt")
        except Exception as e:
            print(f"[Clustering] Gemini API failed: {e}")
