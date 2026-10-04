# ProctorAI Design System & Accessibility Standards

## 🎯 Mandatory Accessibility Rule: WCAG AA & AAA Color Contrast

> [!IMPORTANT]
> **HARD RULE GOING FORWARD**:
> Every text element rendered on a background must be mathematically verified against WCAG AA contrast standards before shipping:
> - **Normal / Body Text (< 18pt / < 14pt bold)**: Minimum **4.5:1** contrast ratio.
> - **Large / Bold Text (≥ 18pt / ≥ 14pt bold) & UI Controls**: Minimum **3.0:1** contrast ratio.
> - **Aim for WCAG AAA (≥ 7.0:1)** on all informational text and alerts.

### 🚫 Strictly Prohibited Pattern: Same-Hue Light-on-Light Pairing
**NEVER** pair a light-tint background with same-hue mid-tone text.  
*Example of Failure*: `bg-amber-950/20` with `text-amber-300` or `bg-amber-100` with `text-amber-400` yields a contrast ratio of only **1.3:1 to 1.7:1**, which is completely illegible.

### ✅ Approved Design Patterns

#### Pattern A — High-Contrast Light Tint Container (Preferred for Alerts & Banners)
Pair a very light background tint (`-50` or `-100`) with **deep `-950` text** and a `-300` border:

| Variant | Background | Border | Primary Text | Accent / Icon | Contrast Ratio | WCAG Rating |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Warning** | `bg-amber-50` (`#fffbeb`) | `border-amber-300` | `text-amber-950` (`#451a03`) | `text-amber-800` (`#92400e`) | **11.47 : 1** | **WCAG AAA** |
| **Error / Alert** | `bg-rose-50` (`#fff1f2`) | `border-rose-300` | `text-rose-950` (`#4c0519`) | `text-rose-800` (`#9f1239`) | **12.45 : 1** | **WCAG AAA** |
| **Success** | `bg-emerald-50` (`#f0fdf4`) | `border-emerald-300` | `text-emerald-950` (`#022c22`) | `text-emerald-800` (`#065f46`) | **12.80 : 1** | **WCAG AAA** |
| **Info / Neutral** | `bg-zinc-100` (`#f4f4f5`) | `border-zinc-300` | `text-zinc-900` (`#18181b`) | `text-zinc-700` (`#3f3f46`) | **12.30 : 1** | **WCAG AAA** |

#### Pattern B — Solid Saturated Badges (High Urgency)
Pair a deep, saturated color (`-700` / `-800`) with solid **white text (`#ffffff`)**:

| Variant | Background | Text Color | Contrast Ratio | WCAG Rating |
| :--- | :--- | :--- | :--- | :--- |
| **Critical Violation** | `bg-rose-700` (`#be123c`) | White (`#ffffff`) | **6.20 : 1** | **WCAG AA** |
| **Verified Benign** | `bg-emerald-700` (`#047857`) | White (`#ffffff`) | **5.59 : 1** | **WCAG AA** |
| **Urgent Warning** | `bg-amber-700` (`#b45309`) | White (`#ffffff`) | **4.82 : 1** | **WCAG AA** |

---

## 🟢 Status Dot & Telemetry Beacon Standards

All live indicators and status dots must adhere to strict bounding rules to prevent flexbox stretching and runaway animation scaling:
1. **Explicit Sizing**: Fixed 8px (`w-2 h-2`) or 10px (`w-2.5 h-2.5`).
2. **Prevent Stretching**: Always include `shrink-0` (`flex-shrink: 0`) and fixed dimensions (`min-w-[8px] min-h-[8px] max-w-[8px] max-h-[8px]`).
3. **Contained Animations**: Any `animate-ping` or `animate-pulse` must reside in a relative wrapper with `pointer-events: none` and bounded expansion rings.
4. **Implementation**: Use `<StatusDot variant="..." ping/pulse />` or `<span className="telemetry-beacon shrink-0" />`.

---

## 🧩 UI Component Reference

All standard UI primitives reside in [`frontend/src/components/ui`](./components/ui):
- **`<Alert variant="warning|error|success|info" onClose={...}>`**: Standard notification and message banner.
- **`<Badge variant="critical|error|warning|success|neutral|outline|dark">`**: Micro status pills.
- **`<StatusDot variant="emerald|amber|rose|zinc" ping={bool} pulse={bool}>`**: Bounded telemetry indicators.
- **`<Button variant="primary|secondary|outline|ghost|destructive">`**: High-contrast interactive controls.
