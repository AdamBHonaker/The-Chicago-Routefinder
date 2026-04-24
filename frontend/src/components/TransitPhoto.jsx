import { useState } from "react";

const PHOTOS = [
  { src: "/transit-photos/red-line-howard.jpg",   caption: "Red Line — Howard" },
  { src: "/transit-photos/loop-elevated.jpg",      caption: "The Loop — Elevated Track" },
  { src: "/transit-photos/blue-line-ohare.jpg",    caption: "Blue Line — O'Hare" },
  { src: "/transit-photos/state-lake.jpg",         caption: "State/Lake — The Loop" },
  { src: "/transit-photos/wrigley-addison.jpg",    caption: "Addison — Wrigley Field" },
];

export default function TransitPhoto({ fading }) {
  const [photo] = useState(
    () => PHOTOS[Math.floor(Math.random() * PHOTOS.length)]
  );
  const [failed, setFailed] = useState(false);

  if (failed) return null;

  return (
    <div className={`transit-photo${fading ? " transit-photo--fading" : ""}`}>
      <img
        src={photo.src}
        alt={photo.caption}
        className="transit-photo-img"
        onError={() => setFailed(true)}
      />
      <p className="transit-photo-caption">{photo.caption}</p>
    </div>
  );
}
