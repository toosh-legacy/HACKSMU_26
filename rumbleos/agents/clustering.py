import multiprocessing as mp
import numpy as np
from pathlib import Path
import json

class ClusteringAgent(mp.Process):
    """
    Stage 7: Pattern clustering + Tribe + Claude API.

    Triggered ONCE when all results are collected (receives list via queue).
    Runs UMAP + K-means, builds Tribe similarity graph, calls Claude API.
    """
    def __init__(self, in_queue, output_dir, claude_api_key=None):
        super().__init__(daemon=True)
        self.in_queue   = in_queue
        self.output_dir = Path(output_dir)
        self.api_key    = claude_api_key

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
        X = StandardScaler().fit_transform(feat_matrix)

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

        # Tribe graph (cosine similarity > 0.80)
        sim   = cosine_similarity(X)
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
        pd.DataFrame(all_results).to_csv(
            self.output_dir / "batch_results_clustered.csv", index=False)

        print(f"[Clustering] {k} clusters | {len(edges)} Tribe edges")
        for c, s in summaries.items():
            print(f"  Cluster {c}: {s['count']} calls | "
                  f"F0={s['mean_f0_hz']}Hz | dur={s['mean_dur_s']}s")

        # Claude API hypotheses (optional)
        if self.api_key:
            self._generate_hypotheses(summaries)

    def _generate_hypotheses(self, summaries: dict):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            total  = sum(v['count'] for v in summaries.values())
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
            resp = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            (self.output_dir / "ai_hypotheses.txt").write_text(resp.content[0].text)
            print("[Clustering] AI hypotheses saved to ai_hypotheses.txt")
        except Exception as e:
            print(f"[Clustering] Claude API failed: {e}")
