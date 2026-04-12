import { createRoot } from 'react-dom/client';
import { NetworkGraph } from './NetworkGraph';
import type { KnowledgeGraph } from './types';

/**
 * Sample graph — simulates a small codebase with folders, files,
 * classes, functions, and various relationship types.
 */
const sampleGraph: KnowledgeGraph = {
  nodes: [
    // Project root
    { id: 'proj', label: 'Project', properties: { name: 'my-app', filePath: '/' } },

    // Folders
    { id: 'src', label: 'Folder', properties: { name: 'src', filePath: '/src' } },
    { id: 'api', label: 'Folder', properties: { name: 'api', filePath: '/src/api' } },
    { id: 'models', label: 'Folder', properties: { name: 'models', filePath: '/src/models' } },
    { id: 'utils', label: 'Folder', properties: { name: 'utils', filePath: '/src/utils' } },
    { id: 'services', label: 'Folder', properties: { name: 'services', filePath: '/src/services' } },

    // Files
    { id: 'f_index', label: 'File', properties: { name: 'index.ts', filePath: '/src/index.ts' } },
    { id: 'f_app', label: 'File', properties: { name: 'app.ts', filePath: '/src/app.ts' } },
    { id: 'f_router', label: 'File', properties: { name: 'router.ts', filePath: '/src/api/router.ts' } },
    { id: 'f_auth', label: 'File', properties: { name: 'auth.ts', filePath: '/src/api/auth.ts' } },
    { id: 'f_user', label: 'File', properties: { name: 'user.ts', filePath: '/src/models/user.ts' } },
    { id: 'f_post', label: 'File', properties: { name: 'post.ts', filePath: '/src/models/post.ts' } },
    { id: 'f_db', label: 'File', properties: { name: 'database.ts', filePath: '/src/utils/database.ts' } },
    { id: 'f_logger', label: 'File', properties: { name: 'logger.ts', filePath: '/src/utils/logger.ts' } },
    { id: 'f_cache', label: 'File', properties: { name: 'cache.ts', filePath: '/src/utils/cache.ts' } },
    { id: 'f_usersvc', label: 'File', properties: { name: 'userService.ts', filePath: '/src/services/userService.ts' } },
    { id: 'f_postsvc', label: 'File', properties: { name: 'postService.ts', filePath: '/src/services/postService.ts' } },
    { id: 'f_email', label: 'File', properties: { name: 'emailService.ts', filePath: '/src/services/emailService.ts' } },

    // Classes
    { id: 'c_user', label: 'Class', properties: { name: 'User', filePath: '/src/models/user.ts' } },
    { id: 'c_post', label: 'Class', properties: { name: 'Post', filePath: '/src/models/post.ts' } },
    { id: 'c_usersvc', label: 'Class', properties: { name: 'UserService', filePath: '/src/services/userService.ts' } },
    { id: 'c_postsvc', label: 'Class', properties: { name: 'PostService', filePath: '/src/services/postService.ts' } },
    { id: 'c_emailsvc', label: 'Class', properties: { name: 'EmailService', filePath: '/src/services/emailService.ts' } },
    { id: 'c_db', label: 'Class', properties: { name: 'Database', filePath: '/src/utils/database.ts' } },
    { id: 'c_cache', label: 'Class', properties: { name: 'CacheManager', filePath: '/src/utils/cache.ts' } },

    // Interfaces
    { id: 'i_repo', label: 'Interface', properties: { name: 'IRepository', filePath: '/src/models/user.ts' } },
    { id: 'i_service', label: 'Interface', properties: { name: 'IService', filePath: '/src/services/userService.ts' } },
    { id: 'i_cacheable', label: 'Interface', properties: { name: 'ICacheable', filePath: '/src/utils/cache.ts' } },

    // Functions
    { id: 'fn_main', label: 'Function', properties: { name: 'main', filePath: '/src/index.ts' } },
    { id: 'fn_setup', label: 'Function', properties: { name: 'setupApp', filePath: '/src/app.ts' } },
    { id: 'fn_routes', label: 'Function', properties: { name: 'registerRoutes', filePath: '/src/api/router.ts' } },
    { id: 'fn_verify', label: 'Function', properties: { name: 'verifyToken', filePath: '/src/api/auth.ts' } },
    { id: 'fn_hash', label: 'Function', properties: { name: 'hashPassword', filePath: '/src/api/auth.ts' } },
    { id: 'fn_log', label: 'Function', properties: { name: 'log', filePath: '/src/utils/logger.ts' } },
    { id: 'fn_connect', label: 'Function', properties: { name: 'connect', filePath: '/src/utils/database.ts' } },
    { id: 'fn_query', label: 'Function', properties: { name: 'runQuery', filePath: '/src/utils/database.ts' } },

    // Methods
    { id: 'm_getuser', label: 'Method', properties: { name: 'getUser', filePath: '/src/services/userService.ts' } },
    { id: 'm_createuser', label: 'Method', properties: { name: 'createUser', filePath: '/src/services/userService.ts' } },
    { id: 'm_deleteuser', label: 'Method', properties: { name: 'deleteUser', filePath: '/src/services/userService.ts' } },
    { id: 'm_getpost', label: 'Method', properties: { name: 'getPost', filePath: '/src/services/postService.ts' } },
    { id: 'm_createpost', label: 'Method', properties: { name: 'createPost', filePath: '/src/services/postService.ts' } },
    { id: 'm_sendemail', label: 'Method', properties: { name: 'sendEmail', filePath: '/src/services/emailService.ts' } },
    { id: 'm_validate', label: 'Method', properties: { name: 'validate', filePath: '/src/models/user.ts' } },
    { id: 'm_serialize', label: 'Method', properties: { name: 'serialize', filePath: '/src/models/user.ts' } },
    { id: 'm_cache_get', label: 'Method', properties: { name: 'get', filePath: '/src/utils/cache.ts' } },
    { id: 'm_cache_set', label: 'Method', properties: { name: 'set', filePath: '/src/utils/cache.ts' } },
  ],
  relationships: [
    // CONTAINS — folder hierarchy
    { id: 'r1', sourceId: 'proj', targetId: 'src', type: 'CONTAINS' },
    { id: 'r2', sourceId: 'src', targetId: 'api', type: 'CONTAINS' },
    { id: 'r3', sourceId: 'src', targetId: 'models', type: 'CONTAINS' },
    { id: 'r4', sourceId: 'src', targetId: 'utils', type: 'CONTAINS' },
    { id: 'r5', sourceId: 'src', targetId: 'services', type: 'CONTAINS' },
    { id: 'r6', sourceId: 'src', targetId: 'f_index', type: 'CONTAINS' },
    { id: 'r7', sourceId: 'src', targetId: 'f_app', type: 'CONTAINS' },
    { id: 'r8', sourceId: 'api', targetId: 'f_router', type: 'CONTAINS' },
    { id: 'r9', sourceId: 'api', targetId: 'f_auth', type: 'CONTAINS' },
    { id: 'r10', sourceId: 'models', targetId: 'f_user', type: 'CONTAINS' },
    { id: 'r11', sourceId: 'models', targetId: 'f_post', type: 'CONTAINS' },
    { id: 'r12', sourceId: 'utils', targetId: 'f_db', type: 'CONTAINS' },
    { id: 'r13', sourceId: 'utils', targetId: 'f_logger', type: 'CONTAINS' },
    { id: 'r14', sourceId: 'utils', targetId: 'f_cache', type: 'CONTAINS' },
    { id: 'r15', sourceId: 'services', targetId: 'f_usersvc', type: 'CONTAINS' },
    { id: 'r16', sourceId: 'services', targetId: 'f_postsvc', type: 'CONTAINS' },
    { id: 'r17', sourceId: 'services', targetId: 'f_email', type: 'CONTAINS' },

    // DEFINES — file defines symbols
    { id: 'r20', sourceId: 'f_user', targetId: 'c_user', type: 'DEFINES' },
    { id: 'r21', sourceId: 'f_post', targetId: 'c_post', type: 'DEFINES' },
    { id: 'r22', sourceId: 'f_usersvc', targetId: 'c_usersvc', type: 'DEFINES' },
    { id: 'r23', sourceId: 'f_postsvc', targetId: 'c_postsvc', type: 'DEFINES' },
    { id: 'r24', sourceId: 'f_email', targetId: 'c_emailsvc', type: 'DEFINES' },
    { id: 'r25', sourceId: 'f_db', targetId: 'c_db', type: 'DEFINES' },
    { id: 'r26', sourceId: 'f_cache', targetId: 'c_cache', type: 'DEFINES' },
    { id: 'r27', sourceId: 'f_user', targetId: 'i_repo', type: 'DEFINES' },
    { id: 'r28', sourceId: 'f_usersvc', targetId: 'i_service', type: 'DEFINES' },
    { id: 'r29', sourceId: 'f_cache', targetId: 'i_cacheable', type: 'DEFINES' },
    { id: 'r30', sourceId: 'f_index', targetId: 'fn_main', type: 'DEFINES' },
    { id: 'r31', sourceId: 'f_app', targetId: 'fn_setup', type: 'DEFINES' },
    { id: 'r32', sourceId: 'f_router', targetId: 'fn_routes', type: 'DEFINES' },
    { id: 'r33', sourceId: 'f_auth', targetId: 'fn_verify', type: 'DEFINES' },
    { id: 'r34', sourceId: 'f_auth', targetId: 'fn_hash', type: 'DEFINES' },
    { id: 'r35', sourceId: 'f_logger', targetId: 'fn_log', type: 'DEFINES' },
    { id: 'r36', sourceId: 'f_db', targetId: 'fn_connect', type: 'DEFINES' },
    { id: 'r37', sourceId: 'f_db', targetId: 'fn_query', type: 'DEFINES' },
    { id: 'r38', sourceId: 'c_usersvc', targetId: 'm_getuser', type: 'DEFINES' },
    { id: 'r39', sourceId: 'c_usersvc', targetId: 'm_createuser', type: 'DEFINES' },
    { id: 'r40', sourceId: 'c_usersvc', targetId: 'm_deleteuser', type: 'DEFINES' },
    { id: 'r41', sourceId: 'c_postsvc', targetId: 'm_getpost', type: 'DEFINES' },
    { id: 'r42', sourceId: 'c_postsvc', targetId: 'm_createpost', type: 'DEFINES' },
    { id: 'r43', sourceId: 'c_emailsvc', targetId: 'm_sendemail', type: 'DEFINES' },
    { id: 'r44', sourceId: 'c_user', targetId: 'm_validate', type: 'DEFINES' },
    { id: 'r45', sourceId: 'c_user', targetId: 'm_serialize', type: 'DEFINES' },
    { id: 'r46', sourceId: 'c_cache', targetId: 'm_cache_get', type: 'DEFINES' },
    { id: 'r47', sourceId: 'c_cache', targetId: 'm_cache_set', type: 'DEFINES' },

    // IMPORTS — file dependencies
    { id: 'r50', sourceId: 'f_index', targetId: 'f_app', type: 'IMPORTS' },
    { id: 'r51', sourceId: 'f_app', targetId: 'f_router', type: 'IMPORTS' },
    { id: 'r52', sourceId: 'f_app', targetId: 'f_db', type: 'IMPORTS' },
    { id: 'r53', sourceId: 'f_app', targetId: 'f_logger', type: 'IMPORTS' },
    { id: 'r54', sourceId: 'f_router', targetId: 'f_auth', type: 'IMPORTS' },
    { id: 'r55', sourceId: 'f_router', targetId: 'f_usersvc', type: 'IMPORTS' },
    { id: 'r56', sourceId: 'f_router', targetId: 'f_postsvc', type: 'IMPORTS' },
    { id: 'r57', sourceId: 'f_usersvc', targetId: 'f_user', type: 'IMPORTS' },
    { id: 'r58', sourceId: 'f_usersvc', targetId: 'f_db', type: 'IMPORTS' },
    { id: 'r59', sourceId: 'f_usersvc', targetId: 'f_cache', type: 'IMPORTS' },
    { id: 'r60', sourceId: 'f_usersvc', targetId: 'f_email', type: 'IMPORTS' },
    { id: 'r61', sourceId: 'f_postsvc', targetId: 'f_post', type: 'IMPORTS' },
    { id: 'r62', sourceId: 'f_postsvc', targetId: 'f_db', type: 'IMPORTS' },

    // CALLS — function call graph
    { id: 'r70', sourceId: 'fn_main', targetId: 'fn_setup', type: 'CALLS' },
    { id: 'r71', sourceId: 'fn_setup', targetId: 'fn_connect', type: 'CALLS' },
    { id: 'r72', sourceId: 'fn_setup', targetId: 'fn_routes', type: 'CALLS' },
    { id: 'r73', sourceId: 'fn_setup', targetId: 'fn_log', type: 'CALLS' },
    { id: 'r74', sourceId: 'fn_routes', targetId: 'fn_verify', type: 'CALLS' },
    { id: 'r75', sourceId: 'm_createuser', targetId: 'fn_hash', type: 'CALLS' },
    { id: 'r76', sourceId: 'm_createuser', targetId: 'fn_query', type: 'CALLS' },
    { id: 'r77', sourceId: 'm_createuser', targetId: 'm_sendemail', type: 'CALLS' },
    { id: 'r78', sourceId: 'm_createuser', targetId: 'm_validate', type: 'CALLS' },
    { id: 'r79', sourceId: 'm_getuser', targetId: 'fn_query', type: 'CALLS' },
    { id: 'r80', sourceId: 'm_getuser', targetId: 'm_cache_get', type: 'CALLS' },
    { id: 'r81', sourceId: 'm_deleteuser', targetId: 'fn_query', type: 'CALLS' },
    { id: 'r82', sourceId: 'm_getpost', targetId: 'fn_query', type: 'CALLS' },
    { id: 'r83', sourceId: 'm_createpost', targetId: 'fn_query', type: 'CALLS' },
    { id: 'r84', sourceId: 'm_createpost', targetId: 'fn_log', type: 'CALLS' },

    // EXTENDS
    { id: 'r90', sourceId: 'c_post', targetId: 'c_user', type: 'EXTENDS' },

    // IMPLEMENTS
    { id: 'r91', sourceId: 'c_usersvc', targetId: 'i_service', type: 'IMPLEMENTS' },
    { id: 'r92', sourceId: 'c_usersvc', targetId: 'i_repo', type: 'IMPLEMENTS' },
    { id: 'r93', sourceId: 'c_cache', targetId: 'i_cacheable', type: 'IMPLEMENTS' },
  ],
  nodeCount: 42,
  relationshipCount: 53,
};

function App() {
  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <NetworkGraph
        graph={sampleGraph}
        onNodeClick={(node) => console.log('Clicked:', node.properties.name, `(${node.label})`)}
      />
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
