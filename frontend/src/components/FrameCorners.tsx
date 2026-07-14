interface Props {
  /** Tailwind border-color class, e.g. "border-gold" or "border-focus" */
  colorClass?: string;
  /** Corner arm length, e.g. "h-5 w-5" */
  sizeClass?: string;
  /** Inset from the container edge, e.g. "inset-2" */
  insetClass?: string;
  className?: string;
}

/**
 * The FaceFind signature: viewfinder corner brackets. Overlay this inside any
 * relatively-positioned container to mark a "finding" moment - the webcam
 * viewport, the loader sweep, a matched photo on hover.
 */
export default function FrameCorners({
  colorClass = 'border-gold',
  sizeClass = 'h-5 w-5',
  insetClass = 'inset-2',
  className = '',
}: Props) {
  return (
    <div aria-hidden className={`pointer-events-none absolute ${insetClass} ${className}`}>
      <span className={`absolute left-0 top-0 ${sizeClass} rounded-tl border-l-2 border-t-2 ${colorClass}`} />
      <span className={`absolute right-0 top-0 ${sizeClass} rounded-tr border-r-2 border-t-2 ${colorClass}`} />
      <span className={`absolute bottom-0 left-0 ${sizeClass} rounded-bl border-b-2 border-l-2 ${colorClass}`} />
      <span className={`absolute bottom-0 right-0 ${sizeClass} rounded-br border-b-2 border-r-2 ${colorClass}`} />
    </div>
  );
}
