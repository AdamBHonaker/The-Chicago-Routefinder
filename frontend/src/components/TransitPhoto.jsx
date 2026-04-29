import { useState } from "react";
import { useTranslation } from "react-i18next";

const PHOTOS = [
  { src: "/transit-photos/red-line-howard.jpg", captionKey: "photo_caption_red_line_howard" },
  { src: "/transit-photos/loop-elevated.jpg",   captionKey: "photo_caption_loop_elevated" },
  { src: "/transit-photos/blue-line-ohare.jpg", captionKey: "photo_caption_blue_line_ohare" },
  { src: "/transit-photos/state-lake.jpg",      captionKey: "photo_caption_state_lake" },
  { src: "/transit-photos/wrigley-addison.jpg", captionKey: "photo_caption_wrigley_addison" },
];

export default function TransitPhoto({ fading }) {
  const { t } = useTranslation();
  const [photo] = useState(
    () => PHOTOS[Math.floor(Math.random() * PHOTOS.length)]
  );
  const [failed, setFailed] = useState(false);

  if (failed) return null;

  const caption = t(photo.captionKey);

  return (
    <div className={`transit-photo${fading ? " transit-photo--fading" : ""}`}>
      <img
        src={photo.src}
        alt={caption}
        className="transit-photo-img"
        onError={() => setFailed(true)}
      />
      <p className="transit-photo-caption">{caption}</p>
    </div>
  );
}
