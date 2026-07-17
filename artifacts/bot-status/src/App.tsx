import { Shield, Activity, Zap, Clock } from 'lucide-react';

function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="border-b border-border px-6 py-4 flex items-center gap-3">
        <Shield className="h-5 w-5 text-primary" />
        <span className="font-semibold text-base tracking-tight">Ivy's Guardian</span>
        <span className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
          </span>
          Online
        </span>
      </header>

      <main className="flex-1 p-6 max-w-xl mx-auto w-full space-y-4">
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
            Bot Status
          </p>
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 rounded-full bg-green-500 shadow-[0_0_6px_1px_rgba(34,197,94,0.6)]" />
            <span className="font-semibold">All systems operational</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Connected to Discord Gateway · Slash commands synced
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-card border border-border rounded-xl p-4 text-center">
            <Zap className="h-4 w-4 text-primary mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">Commands</p>
            <p className="font-semibold mt-0.5">27</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-4 text-center">
            <Activity className="h-4 w-4 text-primary mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">Deployment</p>
            <p className="font-semibold mt-0.5">Reserved VM</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-4 text-center">
            <Clock className="h-4 w-4 text-primary mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">Uptime</p>
            <p className="font-semibold mt-0.5">24 / 7</p>
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-5 space-y-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Modules
          </p>
          {[
            { name: 'Moderation', status: 'Active' },
            { name: 'Music', status: 'Active' },
            { name: 'Utility', status: 'Active' },
            { name: 'Fun', status: 'Active' },
            { name: 'Welcome', status: 'Active' },
          ].map((mod) => (
            <div key={mod.name} className="flex items-center justify-between text-sm">
              <span className="text-foreground">{mod.name}</span>
              <span className="flex items-center gap-1.5 text-green-500 text-xs font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                {mod.status}
              </span>
            </div>
          ))}
        </div>
      </main>

      <footer className="border-t border-border px-6 py-3 text-center text-xs text-muted-foreground">
        Ivy's Guardian · Powered by discord.py · Hosted on Replit Reserved VM
      </footer>
    </div>
  );
}

export default function App() {
  return <Home />;
}
