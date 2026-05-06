// Minimal flat-config ESLint setup (TD-FE-018).
//
// Goal: enforce the two rules whose violations we already silence with
// per-line `// eslint-disable-line react-hooks/exhaustive-deps` comments —
// without those rules being live anywhere, the comments document intent but
// don't catch anything in unmarked hooks.
//
// Run: `npm run lint`. CI hookup is up to whichever workflow exists; locally,
// `npm run lint` should be clean before opening a PR.

import js from "@eslint/js";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  {
    ignores: ["dist/**", "node_modules/**", "public/**"],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      // The two rules our existing disable comments target. Anything else is
      // out of scope for this initial config — keep noise low so the lint
      // signal stays meaningful.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",

      // Quality-of-life relaxations for this codebase's existing style:
      // `_load`, `_save`, etc. are intentional file-private helpers.
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      // React 17+ JSX transform doesn't need React in scope.
      "react/react-in-jsx-scope": "off",
      // PropTypes is not used; types live in JSDoc comments.
      "react/prop-types": "off",
    },
  },
  {
    files: ["src/tests/**/*.{js,jsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        // Vitest globals (vitest.config has globals: true).
        describe: "readonly",
        it: "readonly",
        test: "readonly",
        expect: "readonly",
        beforeAll: "readonly",
        beforeEach: "readonly",
        afterAll: "readonly",
        afterEach: "readonly",
        vi: "readonly",
      },
    },
  },
];
