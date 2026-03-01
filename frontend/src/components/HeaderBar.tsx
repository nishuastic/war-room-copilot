import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, Radio } from "lucide-react";
import type { ConnectionStatus } from "@/hooks/useIncidentStream";

interface HeaderBarProps {
  connectionStatus: ConnectionStatus;
  elapsed: string;
  messageCount: number;
}

const HeaderBar = ({ connectionStatus, elapsed, messageCount }: HeaderBarProps) => {
  const [title, setTitle] = useState("Database Connection Pool Exhaustion");
  const [status, setStatus] = useState("investigating");
  const isConnected = connectionStatus === "connected";

  return (
    <header className="h-14 flex items-center justify-between px-4 border-b border-border bg-card/80 backdrop-blur-sm shrink-0">
      {/* Left */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-foreground" />
          <span className="font-semibold text-foreground text-sm">War Room Copilot</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full animate-pulse-dot ${isConnected ? "bg-wr-green" : "bg-wr-red"}`} />
          <span className={`text-xs ${isConnected ? "text-wr-green" : "text-wr-red"}`}>
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Center */}
      <div className="flex items-center gap-2 flex-1 justify-center max-w-xl min-w-0 overflow-hidden">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="bg-transparent border-none text-foreground text-sm font-medium text-center w-full focus:outline-none focus:ring-1 focus:ring-ring rounded px-2 py-1 truncate"
        />
        <Badge variant="destructive" className="shrink-0 text-[10px] font-mono">SEV-1</Badge>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[130px] h-8 text-xs bg-secondary border-border shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="investigating">Investigating</SelectItem>
            <SelectItem value="identified">Identified</SelectItem>
            <SelectItem value="monitoring">Monitoring</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="font-mono text-wr-amber text-sm tabular-nums">{elapsed}</span>
        <Badge variant="secondary" className="font-mono text-xs">{messageCount} events</Badge>
        <Button variant="ghost" size="sm" className="text-muted-foreground">
          <Download className="w-4 h-4" />
          <span className="hidden lg:inline">Export</span>
        </Button>
      </div>
    </header>
  );
};

export default HeaderBar;
