import { Composition } from "remotion";
import { ShellInstagramReel } from "./ShellInstagramReel";

export const FPS = 30;
export const DURATION_SECONDS = 60;

export const RemotionRoot = () => {
  return (
    <Composition
      id="ShellInstagramReel"
      component={ShellInstagramReel}
      durationInFrames={FPS * DURATION_SECONDS}
      fps={FPS}
      height={1920}
      width={1080}
    />
  );
};
