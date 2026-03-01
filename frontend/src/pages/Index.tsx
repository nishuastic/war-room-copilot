import { useState } from "react";
import { useIncidentStream } from "@/hooks/useIncidentStream";
import HeaderBar from "@/components/HeaderBar";
import SiriOrb from "@/components/SiriOrb";
import TranscriptFeed from "@/components/TranscriptFeed";
import AgentGraph from "@/components/AgentGraph";
import AgentReasoning from "@/components/AgentReasoning";
import RightColumn from "@/components/RightColumn";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { PanelRight } from "lucide-react";
import { useIsMobile } from "@/hooks/use-mobile";

const Index = () => {
  const stream = useIncidentStream();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Mobile: tab navigation
  if (isMobile) {
    return (
      <div className="h-screen flex flex-col bg-background overflow-hidden">
        <HeaderBar connectionStatus={stream.connectionStatus} elapsed={stream.formatElapsed()} messageCount={stream.messages.length} />
        <Tabs defaultValue="transcript" className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="bg-secondary/50 mx-3 mt-2 shrink-0">
            <TabsTrigger value="transcript" className="text-xs">Transcript</TabsTrigger>
            <TabsTrigger value="graph" className="text-xs">Agent</TabsTrigger>
            <TabsTrigger value="context" className="text-xs">Context</TabsTrigger>
          </TabsList>
          <TabsContent value="transcript" className="flex-1 overflow-hidden mt-0">
            <div className="flex flex-col h-full glass-card m-2">
              <SiriOrb state={stream.orbState} />
              <ActiveSpeakers speakers={stream.speakers} />
              <TranscriptFeed messages={stream.messages} speakers={stream.speakers} />
            </div>
          </TabsContent>
          <TabsContent value="graph" className="flex-1 overflow-hidden mt-0">
            <div className="flex flex-col h-full gap-2 m-2">
              <div className="glass-card flex-1 min-h-0">
                <div className="panel-header px-3 pt-2">Agent Graph</div>
                <AgentGraph nodes={stream.graphNodes} links={stream.graphLinks} />
              </div>
              <div className="glass-card flex-1 min-h-0">
                <AgentReasoning traceSteps={stream.traceSteps} findings={stream.findings} />
              </div>
            </div>
          </TabsContent>
          <TabsContent value="context" className="flex-1 overflow-hidden mt-0">
            <div className="glass-card m-2 h-full">
              <RightColumn decisions={stream.decisions} timeline={stream.timeline} findings={stream.findings} messageCount={stream.messages.length} elapsed={stream.formatElapsed()} />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    );
  }

  // Desktop / Tablet
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <HeaderBar connectionStatus={stream.connectionStatus} elapsed={stream.formatElapsed()} messageCount={stream.messages.length} />
      <div className="flex-1 grid grid-cols-[2fr_1.75fr_1.25fr] gap-3 p-3 min-h-0 max-lg:grid-cols-[1fr_1fr] max-lg:grid-rows-[1fr_1fr]">
        {/* Left Column */}
        <div className="glass-card flex flex-col min-h-0 max-lg:row-span-1">
          <div className="panel-header px-3 pt-2">Live Transcript</div>
          <SiriOrb state={stream.orbState} />
          <ActiveSpeakers speakers={stream.speakers} />
          <TranscriptFeed messages={stream.messages} speakers={stream.speakers} />
        </div>

        {/* Center Column */}
        <div className="flex flex-col gap-3 min-h-0 max-lg:row-span-1">
          <div className="glass-card flex-[55] min-h-0 flex flex-col">
            <div className="panel-header px-3 pt-2">Agent Graph</div>
            <div className="flex-1 min-h-0">
              <AgentGraph nodes={stream.graphNodes} links={stream.graphLinks} />
            </div>
          </div>
          <div className="glass-card flex-[45] min-h-0 flex flex-col">
            <div className="panel-header px-3 pt-2">Agent Reasoning</div>
            <div className="flex-1 min-h-0 overflow-hidden">
              <AgentReasoning traceSteps={stream.traceSteps} findings={stream.findings} />
            </div>
          </div>
        </div>

        {/* Right Column — drawer on tablet */}
        <div className="glass-card min-h-0 max-lg:hidden">
          <RightColumn decisions={stream.decisions} timeline={stream.timeline} findings={stream.findings} messageCount={stream.messages.length} elapsed={stream.formatElapsed()} />
        </div>
        <div className="hidden max-lg:block fixed bottom-4 right-4 z-50">
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button size="icon" className="rounded-full shadow-lg">
                <PanelRight className="w-5 h-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="bottom" className="h-[60vh] bg-card border-border">
              <SheetTitle className="panel-header">Incident Context</SheetTitle>
              <RightColumn decisions={stream.decisions} timeline={stream.timeline} findings={stream.findings} messageCount={stream.messages.length} elapsed={stream.formatElapsed()} />
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </div>
  );
};

const ActiveSpeakers = ({ speakers }: { speakers: { id: number; name: string; colorVar: string }[] }) => {
  const colors: Record<number, string> = { 1: "#38bdf8", 2: "#fb7185", 3: "#fbbf24", 4: "#34d399" };
  return (
    <div className="flex items-center gap-3 px-3 py-1.5 flex-wrap">
      {speakers.map((s) => (
        <div key={s.id} className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[s.id] }} />
          <span className="text-xs text-muted-foreground">{s.name}</span>
        </div>
      ))}
    </div>
  );
};

export default Index;
