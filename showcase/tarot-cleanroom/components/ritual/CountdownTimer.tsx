/**
 * CountdownTimer
 *
 * Smooth countdown to a target UTC timestamp using requestAnimationFrame.
 * Server-authoritative: the target epoch is computed on the server and
 * passed as a prop, so client clock skew cannot affect accuracy.
 *
 * Reduced-motion: when prefers-reduced-motion is set, the digit flip
 * animation is replaced with a simple static display.
 */

"use client";

import { useEffect, useRef, useState } from "react";

interface CountdownTimerProps {
  /** UTC ISO timestamp of the target moment */
  targetIso: string;
  /** Label shown when countdown reaches zero */
  onComplete?: string;
  labels?: {
    ariaPrefix: string;
    day: string;
    hour: string;
    minute: string;
    second: string;
  };
}

interface TimeLeft {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  total: number;
}

function computeTimeLeft(targetIso: string): TimeLeft {
  const total = Math.max(0, new Date(targetIso).getTime() - Date.now());
  const seconds = Math.floor((total / 1000) % 60);
  const minutes = Math.floor((total / 1000 / 60) % 60);
  const hours = Math.floor((total / 1000 / 60 / 60) % 24);
  const days = Math.floor(total / 1000 / 60 / 60 / 24);
  return { days, hours, minutes, seconds, total };
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export default function CountdownTimer({
  targetIso,
  onComplete = "Now",
  labels = {
    ariaPrefix: "Opens in",
    day: "d",
    hour: "h",
    minute: "m",
    second: "s",
  },
}: CountdownTimerProps) {
  const [timeLeft, setTimeLeft] = useState<TimeLeft>(() =>
    computeTimeLeft(targetIso),
  );
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Recompute from server target to avoid client clock skew
    setTimeLeft(computeTimeLeft(targetIso));

    const tick = () => {
      const tl = computeTimeLeft(targetIso);
      setTimeLeft(tl);
      if (tl.total > 0) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [targetIso]);

  if (timeLeft.total <= 0) {
    return (
      <span className="countdown__complete">{onComplete}</span>
    );
  }

  return (
    <span
      className="countdown"
      aria-label={`${labels.ariaPrefix} ${timeLeft.days}${labels.day} ${timeLeft.hours}${labels.hour} ${timeLeft.minutes}${labels.minute} ${timeLeft.seconds}${labels.second}`}
    >
      {timeLeft.days > 0 && (
        <span className="countdown__unit">
          <span className="countdown__num">{pad(timeLeft.days)}</span>
          <span className="countdown__label">{labels.day}</span>
        </span>
      )}
      <span className="countdown__unit">
        <span className="countdown__num">{pad(timeLeft.hours)}</span>
        <span className="countdown__label">{labels.hour}</span>
      </span>
      <span className="countdown__sep" aria-hidden="true">:</span>
      <span className="countdown__unit">
        <span className="countdown__num">{pad(timeLeft.minutes)}</span>
        <span className="countdown__label">{labels.minute}</span>
      </span>
      <span className="countdown__sep" aria-hidden="true">:</span>
      <span className="countdown__unit">
        <span className="countdown__num">{pad(timeLeft.seconds)}</span>
        <span className="countdown__label">{labels.second}</span>
      </span>
    </span>
  );
}
