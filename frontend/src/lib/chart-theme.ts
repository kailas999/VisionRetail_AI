/** Theme-aware chart colors — synced with styles.css palette */
export function getChartTheme(isDark: boolean) {
  return {
    grid: isDark ? "oklch(0.74 0.18 285 / 0.08)" : "oklch(0.16 0.035 285 / 0.07)",
    axis: isDark ? "oklch(0.68 0.028 285)" : "oklch(0.46 0.025 285)",
    tooltip: {
      background: isDark ? "oklch(0.28 0.045 285 / 0.97)" : "oklch(0.995 0.006 285 / 0.98)",
      border: isDark ? "1px solid oklch(0.74 0.18 285 / 0.22)" : "1px solid oklch(0.52 0.24 285 / 0.12)",
      borderRadius: 14,
      boxShadow: isDark
        ? "0 12px 40px oklch(0.10 0.04 285 / 0.5), 0 0 0 1px oklch(0.74 0.18 285 / 0.1)"
        : "0 12px 32px oklch(0.52 0.24 285 / 0.12), 0 0 0 1px oklch(0.52 0.24 285 / 0.06)",
      fontSize: 12,
    },
    label: isDark ? "oklch(0.96 0.012 285)" : "oklch(0.16 0.035 285)",
    cursor: isDark ? "oklch(0.74 0.18 285 / 0.1)" : "oklch(0.52 0.24 285 / 0.06)",
    stroke: isDark ? "oklch(0.30 0.048 285)" : "oklch(0.995 0.006 285)",
    primary: isDark ? "oklch(0.74 0.18 285)" : "oklch(0.52 0.24 285)",
    teal: isDark ? "oklch(0.76 0.13 175)" : "oklch(0.58 0.16 175)",
    primaryFill: isDark ? 0.38 : 0.30,
    tealFill: isDark ? 0.38 : 0.30,
  };
}
