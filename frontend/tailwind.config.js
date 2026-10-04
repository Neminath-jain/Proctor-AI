/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "surface": "#fdf8f8",
        "surface-container-highest": "#e5e2e1",
        "surface-container": "#f1edec",
        "surface-container-low": "#f7f3f2",
        "surface-container-high": "#ebe7e6",
        "surface-bright": "#fdf8f8",
        "surface-dim": "#ddd9d8",
        "surface-variant": "#e5e2e1",
        "surface-container-lowest": "#ffffff",
        "primary": "#09090b",
        "primary-container": "#18181b",
        "on-primary": "#ffffff",
        "on-primary-container": "#858383",
        "secondary": "#5e5e5e",
        "secondary-container": "#e1dfdf",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#626262",
        "on-surface": "#09090b",
        "on-surface-variant": "#444748",
        "outline": "#747878",
        "outline-variant": "#c4c7c7",
        "background": "#fdf8f8",
        "on-background": "#09090b",
        "error": "#ba1a1a",
        "error-container": "#ffdad6",
        "on-error": "#ffffff",
        "on-error-container": "#93000a",
        // Desaturated muted semantic colors matching monochrome calm aesthetic
        "success": "#2d6335",
        "success-container": "#dbeef0",
        "on-success": "#ffffff",
        "on-success-container": "#143719",
        "warning": "#7a5912",
        "warning-container": "#fcedd7",
        "on-warning": "#ffffff",
        "on-warning-container": "#422e03"
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
        full: "9999px"
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"]
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.04)',
        'terminal': '0 1px 3px 0 rgba(0, 0, 0, 0.07), 0 1px 2px -1px rgba(0, 0, 0, 0.05)',
        'elevation': '0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.04)',
        'inset-subtle': 'inset 0 1px 1px 0 rgba(0, 0, 0, 0.03)',
      }
    },
  },
  plugins: [],
}
