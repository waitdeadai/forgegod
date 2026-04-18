export default function TarotEmblem({
  size = 48,
}: {
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <circle
        cx="24"
        cy="24"
        r="22"
        stroke="#44d9f3"
        strokeWidth="1.5"
        strokeOpacity="0.4"
      />
      <circle
        cx="24"
        cy="24"
        r="16"
        stroke="#44d9f3"
        strokeWidth="1"
        strokeOpacity="0.25"
      />
      <text
        x="24"
        y="29"
        textAnchor="middle"
        fontFamily="var(--font-display)"
        fontSize="14"
        fontWeight="800"
        fill="#44d9f3"
        letterSpacing="-0.05em"
      >
        1
      </text>
      <path
        d="M24 4 L42 40 L6 40 Z"
        stroke="#44d9f3"
        strokeWidth="1"
        strokeOpacity="0.3"
        fill="none"
      />
    </svg>
  );
}
