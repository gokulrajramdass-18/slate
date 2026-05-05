/**
 * Generate a consistent color for a tag based on its name
 * Returns inline style object for reliable color rendering
 */
export function getTagColorStyle(tag: string): {
  backgroundColor: string;
  color: string;
  borderColor: string;
} {
  // Simple hash function
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  }

  // Color palette - vibrant and distinct colors with inline RGB values
  const colors = [
    { bg: "rgb(219, 234, 254)", text: "rgb(29, 78, 216)", border: "rgb(191, 219, 254)" }, // Blue
    { bg: "rgb(220, 252, 231)", text: "rgb(21, 128, 61)", border: "rgb(187, 247, 208)" }, // Green
    { bg: "rgb(243, 232, 255)", text: "rgb(126, 34, 206)", border: "rgb(233, 213, 255)" }, // Purple
    { bg: "rgb(252, 231, 243)", text: "rgb(190, 24, 93)", border: "rgb(251, 207, 232)" }, // Pink
    { bg: "rgb(255, 237, 213)", text: "rgb(194, 65, 12)", border: "rgb(254, 215, 170)" }, // Orange
    { bg: "rgb(204, 251, 241)", text: "rgb(15, 118, 110)", border: "rgb(153, 246, 228)" }, // Teal
    { bg: "rgb(224, 231, 255)", text: "rgb(67, 56, 202)", border: "rgb(199, 210, 254)" }, // Indigo
    { bg: "rgb(255, 228, 230)", text: "rgb(190, 18, 60)", border: "rgb(254, 205, 211)" }, // Rose
    { bg: "rgb(207, 250, 254)", text: "rgb(14, 116, 144)", border: "rgb(165, 243, 252)" }, // Cyan
    { bg: "rgb(254, 243, 199)", text: "rgb(180, 83, 9)", border: "rgb(253, 230, 138)" }, // Amber
    { bg: "rgb(236, 252, 203)", text: "rgb(77, 124, 15)", border: "rgb(217, 249, 157)" }, // Lime
    { bg: "rgb(209, 250, 229)", text: "rgb(5, 150, 105)", border: "rgb(167, 243, 208)" }, // Emerald
  ];

  // Use absolute value to ensure positive index
  const index = Math.abs(hash) % colors.length;
  return {
    backgroundColor: colors[index].bg,
    color: colors[index].text,
    borderColor: colors[index].border,
  };
}

/**
 * Get dark mode color style for tags
 */
export function getTagColorStyleDark(tag: string): {
  backgroundColor: string;
  color: string;
  borderColor: string;
} {
  // Simple hash function
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  }

  // Dark mode colors - muted backgrounds with bright text
  const colors = [
    { bg: "rgba(30, 58, 138, 0.3)", text: "rgb(147, 197, 253)", border: "rgb(30, 58, 138)" }, // Blue
    { bg: "rgba(20, 83, 45, 0.3)", text: "rgb(134, 239, 172)", border: "rgb(20, 83, 45)" }, // Green
    { bg: "rgba(107, 33, 168, 0.3)", text: "rgb(216, 180, 254)", border: "rgb(107, 33, 168)" }, // Purple
    { bg: "rgba(157, 23, 77, 0.3)", text: "rgb(251, 207, 232)", border: "rgb(157, 23, 77)" }, // Pink
    { bg: "rgba(154, 52, 18, 0.3)", text: "rgb(253, 186, 116)", border: "rgb(154, 52, 18)" }, // Orange
    { bg: "rgba(17, 94, 89, 0.3)", text: "rgb(153, 246, 228)", border: "rgb(17, 94, 89)" }, // Teal
    { bg: "rgba(55, 48, 163, 0.3)", text: "rgb(199, 210, 254)", border: "rgb(55, 48, 163)" }, // Indigo
    { bg: "rgba(159, 18, 57, 0.3)", text: "rgb(254, 205, 211)", border: "rgb(159, 18, 57)" }, // Rose
    { bg: "rgba(21, 94, 117, 0.3)", text: "rgb(165, 243, 252)", border: "rgb(21, 94, 117)" }, // Cyan
    { bg: "rgba(146, 64, 14, 0.3)", text: "rgb(252, 211, 77)", border: "rgb(146, 64, 14)" }, // Amber
    { bg: "rgba(63, 98, 18, 0.3)", text: "rgb(217, 249, 157)", border: "rgb(63, 98, 18)" }, // Lime
    { bg: "rgba(6, 95, 70, 0.3)", text: "rgb(167, 243, 208)", border: "rgb(6, 95, 70)" }, // Emerald
  ];

  const index = Math.abs(hash) % colors.length;
  return {
    backgroundColor: colors[index].bg,
    color: colors[index].text,
    borderColor: colors[index].border,
  };
}
