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
        <label className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1">
          <Moon className="h-3.5 w-3.5 text-muted-foreground" />
          <Switch checked={isLight} onCheckedChange={handleChange} />
          <Sun className="h-3.5 w-3.5 text-muted-foreground" />
        </label>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        {isLight ? "Light mode" : "Dark mode"}
      </TooltipContent>
    </Tooltip>
  );
}
