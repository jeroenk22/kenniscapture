import { cn } from "@/lib/utils";

export type LoaderVariant = "dots" | "typing" | "circular";

export interface LoaderProps {
  variant?: LoaderVariant;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const DOT_DELAYS = [0, 160, 320] as const;
const TYPING_DELAYS = [0, 250, 500] as const;

function DotsLoader({ className, size = "md" }: { className?: string; size?: "sm" | "md" | "lg" }) {
  const dotSizes = { sm: "h-1.5 w-1.5", md: "h-2 w-2", lg: "h-2.5 w-2.5" };
  const containerSizes = { sm: "h-4", md: "h-5", lg: "h-6" };

  return (
    <div className={cn("flex items-center space-x-1", containerSizes[size], className)}>
      {DOT_DELAYS.map((delay) => (
        <div
          key={delay}
          className={cn("bg-primary animate-bounce rounded-full", dotSizes[size])}
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
      <span className="sr-only">Laden...</span>
    </div>
  );
}

function CircularLoader({
  className,
  size = "md",
}: {
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClasses = { sm: "size-4", md: "size-5", lg: "size-6" };
  return (
    <div
      className={cn(
        "border-primary animate-spin rounded-full border-2 border-t-transparent",
        sizeClasses[size],
        className,
      )}
    >
      <span className="sr-only">Laden...</span>
    </div>
  );
}

function TypingLoader({
  className,
  size = "md",
}: {
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const dotSizes = { sm: "h-1 w-1", md: "h-1.5 w-1.5", lg: "h-2 w-2" };
  const containerSizes = { sm: "h-4", md: "h-5", lg: "h-6" };

  return (
    <div className={cn("flex items-center space-x-1", containerSizes[size], className)}>
      {TYPING_DELAYS.map((delay) => (
        <div
          key={delay}
          className={cn("bg-muted-foreground animate-bounce rounded-full", dotSizes[size])}
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
      <span className="sr-only">Typen...</span>
    </div>
  );
}

function Loader({ variant = "dots", size = "md", className }: LoaderProps) {
  switch (variant) {
    case "typing":
      return <TypingLoader size={size} className={className} />;
    case "circular":
      return <CircularLoader size={size} className={className} />;
    default:
      return <DotsLoader size={size} className={className} />;
  }
}

export { Loader };
