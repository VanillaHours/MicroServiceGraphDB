/*
 * P2 contract-plane path emitter — libyang 2.1.148 compiled schema walk.
 *
 * Loads FRR's YANG modules into one libyang context (the same job FRR's
 * nb_info_new world lives in), then walks every compiled tree and emits one
 * JSONL row per schema node:
 *
 *   module       defining module of the node (augments keep THEIR module)
 *   tree_module  module whose compiled tree the node was found in (the
 *                augment target for augmented nodes)
 *   name/nodetype
 *   schema_path  libyang LYSC_PATH_SCHEMA  (choice/case kept, module-qualified)
 *   data_path    libyang LYSC_PATH_DATA    (data nodes only)
 *   bare         P1-convention path: data-only segments, no module prefixes,
 *                restarts at the augment root -> matches yang:<mod>:<bare>
 *
 * Read:  argv[1] = colon-separated search dirs
 *        argv[2] = output .jsonl path
 *        stdin   = module names, one per line (features "*" enabled)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libyang/libyang.h>

#define BUF 16384

static const char *nodetype_str(uint16_t t)
{
        switch (t) {
        case LYS_CONTAINER:  return "container";
        case LYS_LIST:       return "list";
        case LYS_LEAF:       return "leaf";
        case LYS_LEAFLIST:   return "leaf-list";
        case LYS_CHOICE:     return "choice";
        case LYS_CASE:       return "case";
        case LYS_ANYDATA:    return "anydata";
        case LYS_ANYXML:     return "anyxml";
        case LYS_RPC:        return "rpc";
        case LYS_ACTION:     return "action";
        case LYS_NOTIF:      return "notification";
        default:             return "other";
        }
}

static int is_data_kind(uint16_t t)
{
        return t == LYS_CONTAINER || t == LYS_LIST || t == LYS_LEAF ||
               t == LYS_LEAFLIST || t == LYS_ANYDATA || t == LYS_ANYXML;
}

static void jstr(const char *s)
{
        putchar('"');
        for (; *s; s++) {
                if (*s == '"' || *s == '\\')
                        putchar('\\');
                putchar(*s);
        }
        putchar('"');
}

static void emit_row(const struct lysc_node *n, const struct lys_module *tree,
                     const char *bare)
{
        char sp[BUF], dp[BUF];

        /* LYSC_PATH_LOG = schema-style path (choice/case kept) — the format FRR
         * NB tables use; LYSC_PATH_DATA = data nodes only. */
        lysc_path((struct lysc_node *)n, LYSC_PATH_LOG, sp, sizeof sp);
        lysc_path((struct lysc_node *)n, LYSC_PATH_DATA, dp, sizeof dp);

        fputs("{\"module\":", stdout); jstr(n->module->name);
        fputs(",\"tree_module\":", stdout); jstr(tree->name);
        fputs(",\"name\":", stdout); jstr(n->name);
        fputs(",\"nodetype\":", stdout); jstr(nodetype_str(n->nodetype));
        fputs(",\"schema_path\":", stdout); jstr(sp);
        fputs(",\"data_path\":", stdout); jstr(dp);
        fputs(",\"bare\":", stdout); jstr(bare);
        fputs("}\n", stdout);
}

#define GETNEXT_OPTS (LYS_GETNEXT_WITHCHOICE | LYS_GETNEXT_WITHCASE)

/* Depth-first walk of one compiled subtree. `bare` accumulates data-segment
 * names and resets whenever the parent belongs to a different module (augment
 * boundary), so yang:<module>:<bare> reproduces the P1 id space: augmented
 * nodes live under their defining module with the augment-local path. */
static void walk_node(const struct lysc_node *n, const struct lys_module *tree,
                      const char *bare_in)
{
        char bare[BUF];
        const struct lysc_node *c;

        if (n->parent && strcmp(n->parent->module->name, n->module->name) != 0)
                bare[0] = '\0';                 /* augment root: restart */
        else
                snprintf(bare, sizeof bare, "%s", bare_in);

        if (is_data_kind(n->nodetype)) {
                size_t len = strlen(bare);
                snprintf(bare + len, sizeof bare - len, "%s%s",
                         len ? "/" : "", n->name);
        }

        emit_row(n, tree, bare);

        for (c = lys_getnext(NULL, n, NULL, GETNEXT_OPTS); c;
             c = lys_getnext(c, n, NULL, GETNEXT_OPTS))
                walk_node(c, tree, bare);
}

static void walk_module(const struct lys_module *mod)
{
        const struct lysc_node *n;

        /* top-level data nodes (libyang splices top-level augments here) */
        for (n = mod->compiled->data; n; n = n->next)
                walk_node(n, mod, "");

        /* top-level RPCs and notifications (frr-zebra has 10 rpcs) */
        for (n = (const struct lysc_node *)mod->compiled->rpcs; n;
             n = n->next)
                walk_node(n, mod, "");
        for (n = (const struct lysc_node *)mod->compiled->notifs; n;
             n = n->next)
                walk_node(n, mod, "");
}

int main(int argc, char **argv)
{
        struct ly_ctx *ctx = NULL;
        struct lys_module *mod;
        char line[512];
        char modname[256];
        int n_load = 0, n_fail = 0;

        if (argc < 3) {
                fprintf(stderr, "usage: %s <search_dirs> <out.jsonl> < names\n",
                        argv[0]);
                return 2;
        }

        if (ly_ctx_new(argv[1], 0, &ctx) != LY_SUCCESS) {
                fprintf(stderr, "ly_ctx_new failed\n");
                return 1;
        }

        while (fgets(line, sizeof line, stdin)) {
                /* line: "<module> [feat1 feat2 ...]" — features enabled explicitly */
                const char *feats[64];
                int nf = 0;

                line[strcspn(line, "\r\n")] = '\0';
                if (!line[0])
                        continue;
                char *tok = strtok(line, " ");
                if (!tok)
                        continue;
                snprintf(modname, sizeof modname, "%s", tok);
                while ((tok = strtok(NULL, " ")) && nf < 63)
                        feats[nf++] = tok;
                feats[nf] = NULL;
                const char **farg = nf ? feats : NULL;

                mod = ly_ctx_load_module(ctx, modname, NULL, farg);
                if (!mod) {
                        fprintf(stderr, "LOAD-FAIL %s\n", modname);
                        n_fail++;
                        continue;
                }
                fprintf(stderr, "LOADED %s (implemented=%d feats=%d)\n", modname,
                        mod->implemented, nf);
                n_load++;
        }
        fprintf(stderr, "loaded=%d failed=%d\n", n_load, n_fail);

        if (!freopen(argv[2], "w", stdout))
                return 1;

        /* Walk every implemented module in the context. Imported std modules
         * (ietf-inet-types etc.) are not implemented, so they yield nothing. */
        {
                uint32_t i = 0;
                struct lys_module *m;

                while ((m = ly_ctx_get_module_iter(ctx, &i)))
                        if (m->implemented && m->compiled)
                                walk_module(m);
        }

        ly_ctx_destroy(ctx);
        return 0;
}
