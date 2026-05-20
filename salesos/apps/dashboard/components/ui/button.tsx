import * as React from "react";

import { cn } from "@/lib/utils";

export function Button({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-full bg-ember-400 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-ember-300",
        className,
      )}
      {...props}
    />
  );
}
