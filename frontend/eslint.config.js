import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import prettier from "eslint-config-prettier";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        document: "readonly",
        fetch: "readonly",
        Intl: "readonly",
      },
      parser: tsParser,
      parserOptions: {
        project: "./tsconfig.json",
      },
    },
    plugins: {
      "@typescript-eslint": tseslint,
      "react-hooks": reactHooks,
    },
    rules: {
      ...tseslint.configs.strict.rules,
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
  prettier,
];
