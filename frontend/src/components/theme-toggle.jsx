import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

// Switches between the dark table and the lighter felt variant (see .light in index.css).
export default function ThemeToggle({ className }) {
  const { resolvedTheme, setTheme } = useTheme();
  const isLight = resolvedTheme === "light";

  return (
    <Button
      size="icon"
      className={className}
      onClick={() => setTheme(isLight ? "dark" : "light")}
      aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
    >
      {isLight ? <Moon /> : <Sun />}
    </Button>
  );
}
