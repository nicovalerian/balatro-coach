import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export default function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const activeTheme = theme === "system" ? resolvedTheme : theme;
  const isLight = activeTheme === "light";

  const handleChange = (checked) => {
    setTheme(checked ? "light" : "dark");
  };

  if (!mounted) {
    return <div className="h-8 w-[4.75rem]" />;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <label className="inline-flex items-center gap-2 rounded-md balatro-card px-3 py-1.5 cursor-pointer hover:scale-105 transition-transform">
          <Moon className="h-4 w-4 text-accent" />
          <Switch checked={isLight} onCheckedChange={handleChange} />
          <Sun className="h-4 w-4 text-primary" />
        </label>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="balatro-card text-xs">
        {isLight ? "Light mode" : "Dark mode"}
      </TooltipContent>
    </Tooltip>
  );
}
