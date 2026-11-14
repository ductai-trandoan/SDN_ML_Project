import React, { useState, useEffect, useMemo } from 'react';
import {
    SystemMetrics, FlowEntry, DecisionLog,
    INITIAL_METRICS, INITIAL_FLOWS, INITIAL_DECISION_LOGS, SCENARIOS
} from './mockData';

// SECTION: COMPONENT_MAIN
export const SDNDashboard: React.FC = () => {
    const [metrics, setMetrics] = useState<SystemMetrics>(INITIAL_METRICS);
    const [flows, setFlows] = useState<FlowEntry[]>(INITIAL_FLOWS);
    const [decisionLogs, setDecisionLogs] = useState<DecisionLog[]>(INITIAL_DECISION_LOGS);
    const [selectedSwitch, setSelectedSwitch] = useState<string>('ALL');
    const [activeScenario, setActiveScenario] = useState<string>('K1');
    const [isLive, setIsLive] = useState<boolean>(true);
    const [epoch, setEpoch] = useState<string>((Date.now() / 1000).toFixed(2));

    const [historyData, setHistoryData] = useState(() => {
        const arr = [];
        const now = Date.now();
        for (let i = 24; i >= 0; i--) {
            arr.push({
                tp: (6.5 + Math.sin(i / 3) * 1.5).toFixed(2),
                rtt: (11.0 + Math.cos(i / 2) * 2.0).toFixed(1)
            });
        }
        return arr;
    });

    const [consoleLogs, setConsoleLogs] = useState<string[]>([
        '14:00:01 OFP_EVENT DPID:0001 (s1) PORT_STATUS:UP',
        '14:00:01 OFP_EVENT DPID:0002 (s2) PORT_STATUS:UP',
        '14:00:01 OFP_EVENT DPID:0006 (s6) PORT_STATUS:UP',
        '14:00:02 TELEMETRY PORT_STATS_REQUEST POLL Δt=1.0s',
        '14:00:03 ML_SERVICE MODEL:RF_BALANCED TREES:100 INFER:ONLINE',
        '14:00:04 CONTROLLER ACTIVE_PATH:P1 FLOW_TABLE:COMMITTED'
    ]);

    // SECTION: EPOCH_TIMER
    useEffect(() => {
        const clock = setInterval(() => {
            setEpoch((Date.now() / 1000).toFixed(2));
        }, 500);
        return () => clearInterval(clock);
    }, []);

    // SECTION: TELEMETRY_FEED_LOOP
    useEffect(() => {
        if (!isLive) return;

        const timer = setInterval(() => {
            fetch('/api/live_data')
                .then(r => r.json())
                .then(data => {
                    if (data && data.active_path) {
                        setMetrics(prev => ({
                            ...prev,
                            activePath: data.active_path,
                            scenario: data.current_scenario || prev.scenario,
                            systemState: data.system_status === 'CONGESTED_ALERT' ? 'CONGESTION_WARNING' : 'ADAPTIVE_STABLE'
                        }));
                    }
                })
                .catch(() => {
                    setMetrics(prev => {
                        const isCong = prev.scenario === 'K4' || prev.scenario === 'K3';
                        const curUtil = isCong ? (prev.activePath === 'P1' ? 88.5 : 32.0) : 68.0 + Math.random() * 5.0;
                        const curRtt = prev.activePath === 'P1' ? (isCong ? 64.2 : 11.5) : 31.0;
                        return {
                            ...prev,
                            avgRtt: parseFloat(curRtt.toFixed(1)),
                            peakUtil: parseFloat(curUtil.toFixed(1)),
                            jitter: parseFloat((0.8 + Math.random() * 0.4).toFixed(2)),
                            packetLoss: isCong && prev.activePath === 'P1' ? 4.2 : 0.02
                        };
                    });
                });

            setHistoryData(prev => {
                const next = [...prev.slice(1)];
                const tpVal = metrics.activePath === 'P1' ? (metrics.scenario === 'K4' ? 4.2 : 8.1) : 8.4;
                next.push({
                    tp: (tpVal + (Math.random() - 0.5) * 0.4).toFixed(2),
                    rtt: metrics.avgRtt.toFixed(1)
                });
                return next;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [isLive, metrics.activePath, metrics.scenario, metrics.avgRtt]);

    // SECTION: SCENARIO_TRIGGER
    const handleSelectScenario = (scId: string) => {
        setActiveScenario(scId);
        fetch('/api/scenario/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenario_id: scId })
        }).catch(() => {});

        setConsoleLogs(prev => [`${new Date().toTimeString().split(' ')[0]} SCENARIO_OVERRIDE ID:${scId}`, ...prev.slice(0, 15)]);
    };

    const filteredFlows = useMemo(() => {
        if (selectedSwitch === 'ALL') return flows;
        return flows.filter(f => f.dpid === selectedSwitch);
    }, [selectedSwitch, flows]);

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-300 font-sans p-3 space-y-2.5 antialiased">
            
            {/* SECTION: TOP_NAV */}
            <header className="border border-zinc-800 bg-zinc-900/90 px-3.5 py-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2.5 font-mono">
                    <span className="h-2 w-2 bg-emerald-500"></span>
                    <span className="font-bold text-white tracking-widest">SDN_ML_ORCHESTRATOR</span>
                    <span className="text-zinc-600">/</span>
                    <span className="text-[11px] text-zinc-500">OF13_RYU_4.34</span>
                </div>

                <div className="flex items-center gap-2 font-mono text-[11px]">
                    <div className="px-2 py-0.5 bg-zinc-950 border border-zinc-800">
                        <span className="text-zinc-500">CTRL_RTT:</span> <span className="text-emerald-400">{metrics.controllerRtt}ms</span>
                    </div>
                    <div className="px-2 py-0.5 bg-zinc-950 border border-zinc-800">
                        <span className="text-zinc-500">ML_INFER:</span> <span className="text-amber-400">{metrics.mlInferenceMs}ms</span>
                    </div>
                    <div className="px-2 py-0.5 bg-zinc-950 border border-zinc-800">
                        <span className="text-zinc-500">EPOCH:</span> <span className="text-zinc-300">{epoch}</span>
                    </div>
                    <button
                        onClick={() => setIsLive(!isLive)}
                        className={`px-2 py-0.5 border text-[10px] font-bold ${
                            isLive ? 'border-emerald-600 bg-emerald-950/40 text-emerald-400' : 'border-zinc-700 bg-zinc-900 text-zinc-500'
                        }`}
                    >
                        {isLive ? 'LIVE' : 'HALT'}
                    </button>
                </div>
            </header>

            {/* SECTION: KPI_TICKER */}
            <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 border border-zinc-800 divide-x divide-y md:divide-y-0 divide-zinc-800 bg-zinc-900/60 font-mono">
                <div className="p-2.5">
                    <div className="text-[10px] text-zinc-500 tracking-wider">RTT_AVG</div>
                    <div className="mt-0.5 flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-white">{metrics.avgRtt}</span>
                        <span className="text-[10px] text-zinc-500">ms</span>
                    </div>
                </div>

                <div className="p-2.5">
                    <div className="text-[10px] text-zinc-500 tracking-wider">JITTER</div>
                    <div className="mt-0.5 flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-white">{metrics.jitter}</span>
                        <span className="text-[10px] text-zinc-500">ms</span>
                    </div>
                </div>

                <div className="p-2.5">
                    <div className="text-[10px] text-zinc-500 tracking-wider">PKT_LOSS</div>
                    <div className="mt-0.5 flex items-baseline gap-1">
                        <span className={`text-2xl font-bold ${metrics.packetLoss > 1.0 ? 'text-red-400' : 'text-white'}`}>
                            {metrics.packetLoss}
                        </span>
                        <span className="text-[10px] text-zinc-500">%</span>
                    </div>
                </div>

                <div className="p-2.5">
                    <div className="text-[10px] text-zinc-500 tracking-wider">MAX_LINK_UTIL</div>
                    <div className="mt-0.5 flex items-baseline gap-1">
                        <span className={`text-2xl font-bold ${metrics.peakUtil >= 80 ? 'text-red-400' : metrics.peakUtil >= 65 ? 'text-amber-400' : 'text-white'}`}>
                            {metrics.peakUtil}
                        </span>
                        <span className="text-[10px] text-zinc-500">%</span>
                    </div>
                </div>

                <div className="p-2.5">
                    <div className="text-[10px] text-zinc-500 tracking-wider">FLOW_RULES</div>
                    <div className="mt-0.5 flex items-baseline gap-1">
                        <span className="text-2xl font-bold text-white">{metrics.activeFlows}</span>
                        <span className="text-[10px] text-zinc-500">ENTRIES</span>
                    </div>
                </div>

                <div className="p-2.5">
                    <div className="text-[10px] text-zinc-500 tracking-wider">ACTIVE_PATH // REROUTE</div>
                    <div className="mt-0.5 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-emerald-400">{metrics.activePath}</span>
                        <span className="text-[11px] text-zinc-400">{metrics.rerouteTime}s</span>
                    </div>
                </div>
            </section>

            {/* SECTION: WORKSPACE_GRID */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-2.5">
                
                {/* SECTION: LEFT_TOPOLOGY_AND_GRAPH */}
                <div className="lg:col-span-7 space-y-2.5">
                    
                    {/* TOPOLOGY_STATUS */}
                    <div className="border border-zinc-800 bg-zinc-900/60 p-2.5 font-mono text-xs">
                        <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-zinc-800 text-[11px]">
                            <span className="font-bold text-zinc-200">TOPOLOGY_MATRIX // 6_OVS_NODES</span>
                            <span className="text-emerald-400 font-bold px-1.5 py-0.2 bg-zinc-950 border border-zinc-800">
                                ACTIVE_ROUTE: {metrics.activePath}
                            </span>
                        </div>

                        <div className="space-y-2">
                            {/* P1 */}
                            <div className={`p-2 border ${metrics.activePath === 'P1' ? 'border-emerald-600/70 bg-zinc-950' : 'border-zinc-850 bg-zinc-950/60'}`}>
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="font-bold text-white">PATH_P1 [s1-s2-s6]</span>
                                    <span className="text-zinc-500">10M // 10ms // 2_HOPS</span>
                                </div>
                                <div className="mt-1.5 grid grid-cols-2 gap-2 text-[10px]">
                                    <div>
                                        <div className="flex justify-between text-zinc-400 mb-0.5">
                                            <span>LINK_s1_s2</span>
                                            <span>{metrics.activePath === 'P1' ? '7.65M (76.5%)' : '0.12M'}</span>
                                        </div>
                                        <div className="w-full bg-zinc-850 h-1">
                                            <div className={`h-1 ${metrics.activePath === 'P1' ? 'bg-emerald-500' : 'bg-zinc-700'}`} style={{ width: metrics.activePath === 'P1' ? '76.5%' : '1.2%' }}></div>
                                        </div>
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-zinc-400 mb-0.5">
                                            <span>LINK_s2_s6</span>
                                            <span className={metrics.peakUtil >= 80 ? 'text-red-400 font-bold' : 'text-zinc-400'}>
                                                {metrics.activePath === 'P1' ? `${metrics.peakUtil}%` : '0.12M'}
                                            </span>
                                        </div>
                                        <div className="w-full bg-zinc-850 h-1">
                                            <div className={`h-1 ${metrics.peakUtil >= 80 ? 'bg-red-500' : metrics.activePath === 'P1' ? 'bg-amber-500' : 'bg-zinc-700'}`} style={{ width: metrics.activePath === 'P1' ? `${metrics.peakUtil}%` : '1.2%' }}></div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* P2 */}
                            <div className={`p-2 border ${metrics.activePath === 'P2' ? 'border-emerald-600/70 bg-zinc-950' : 'border-zinc-850 bg-zinc-950/60'}`}>
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="font-bold text-white">PATH_P2 [s1-s3-s4-s6]</span>
                                    <span className="text-zinc-500">10M // 30ms // 3_HOPS</span>
                                </div>
                                <div className="mt-1.5 text-[10px]">
                                    <div className="flex justify-between text-zinc-400 mb-0.5">
                                        <span>AGG_UTIL [s1-s3-s4-s6]</span>
                                        <span>{metrics.activePath === 'P2' ? '8.42M (84.2%)' : 'IDLE'}</span>
                                    </div>
                                    <div className="w-full bg-zinc-850 h-1">
                                        <div className={`h-1 ${metrics.activePath === 'P2' ? 'bg-emerald-500' : 'bg-zinc-800'}`} style={{ width: metrics.activePath === 'P2' ? '84.2%' : '0%' }}></div>
                                    </div>
                                </div>
                            </div>

                            {/* P3 */}
                            <div className={`p-2 border ${metrics.activePath === 'P3' ? 'border-emerald-600/70 bg-zinc-950' : 'border-zinc-850 bg-zinc-950/60'}`}>
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="font-bold text-white">PATH_P3 [s1-s5-s6]</span>
                                    <span className="text-zinc-500">5M // 20ms // 2_HOPS</span>
                                </div>
                                <div className="mt-1.5 text-[10px]">
                                    <div className="flex justify-between text-zinc-400 mb-0.5">
                                        <span>LINK_s1_s5_s6</span>
                                        <span>{metrics.activePath === 'P3' ? '3.80M (76.0%)' : 'IDLE'}</span>
                                    </div>
                                    <div className="w-full bg-zinc-850 h-1">
                                        <div className={`h-1 ${metrics.activePath === 'P3' ? 'bg-emerald-500' : 'bg-zinc-800'}`} style={{ width: metrics.activePath === 'P3' ? '76.0%' : '0%' }}></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* TELEMETRY_STREAM_CHART */}
                    <div className="border border-zinc-800 bg-zinc-900/60 p-2.5 font-mono">
                        <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-zinc-800 text-[11px]">
                            <span className="font-bold text-zinc-200">TELEMETRY_STREAM // INGRESS_TP vs RTT</span>
                            <div className="flex items-center gap-3 text-[10px]">
                                <span className="text-emerald-400 font-bold">TP (Mbps)</span>
                                <span className="text-amber-400 font-bold">RTT (ms)</span>
                                <span className="text-red-400">THRESH (8.0M)</span>
                            </div>
                        </div>

                        <div className="h-40 w-full bg-zinc-950 border border-zinc-850 p-1.5 relative">
                            <svg className="w-full h-full overflow-visible" viewBox="0 0 500 110" preserveAspectRatio="none">
                                <line x1="0" y1="20" x2="500" y2="20" stroke="#1f242f" strokeWidth="0.8" strokeDasharray="2,2" />
                                <line x1="0" y1="50" x2="500" y2="50" stroke="#1f242f" strokeWidth="0.8" strokeDasharray="2,2" />
                                <line x1="0" y1="80" x2="500" y2="80" stroke="#1f242f" strokeWidth="0.8" strokeDasharray="2,2" />
                                <line x1="0" y1="105" x2="500" y2="105" stroke="#27272a" strokeWidth="0.8" />
                                <line x1="0" y1="35" x2="500" y2="35" stroke="#ef4444" strokeWidth="1" strokeDasharray="3,3" />

                                <polyline
                                    fill="none"
                                    stroke="#10b981"
                                    strokeWidth="1.5"
                                    points={historyData.map((d, i) => `${(i / (historyData.length - 1)) * 500},${105 - (parseFloat(d.tp) / 10.0) * 85}`).join(' ')}
                                />
                                <polyline
                                    fill="none"
                                    stroke="#f59e0b"
                                    strokeWidth="1.2"
                                    points={historyData.map((d, i) => `${(i / (historyData.length - 1)) * 500},${105 - (parseFloat(d.rtt) / 80.0) * 85}`).join(' ')}
                                />
                            </svg>
                            <div className="absolute top-1 left-2 text-[9px] text-zinc-500 font-mono">10M // 80ms</div>
                            <div className="absolute bottom-1 right-2 text-[9px] text-zinc-500 font-mono">WINDOW:25s Δt:1s</div>
                        </div>
                    </div>
                </div>

                {/* SECTION: RIGHT_ML_AND_EVENTS */}
                <div className="lg:col-span-5 space-y-2.5 font-mono">
                    
                    {/* ML_INFERENCE_TELEMETRY */}
                    <div className="border border-zinc-800 bg-zinc-900/60 p-2.5 text-xs">
                        <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-zinc-800 text-[11px]">
                            <span className="font-bold text-zinc-200">ML_ENGINE // EARLY_PREDICTION</span>
                            <span className="text-emerald-400">F1:99.2% | AUC:0.989</span>
                        </div>

                        <div className="space-y-2">
                            <div className="p-2 bg-zinc-950 border border-zinc-850">
                                <div className="flex justify-between text-[10px] text-zinc-400 mb-1">
                                    <span>CONGESTION_RISK_H5</span>
                                    <span className={metrics.peakUtil >= 80 ? 'text-red-400 font-bold' : 'text-emerald-400'}>
                                        {metrics.peakUtil >= 80 ? '94.2%' : '8.4%'}
                                    </span>
                                </div>
                                <div className="w-full bg-zinc-850 h-1.5">
                                    <div
                                        className={`h-1.5 ${metrics.peakUtil >= 80 ? 'bg-red-500' : metrics.peakUtil >= 65 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                                        style={{ width: metrics.peakUtil >= 80 ? '94.2%' : '8.4%' }}
                                    ></div>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                                <div className="p-1.5 bg-zinc-950 border border-zinc-850">
                                    <div className="text-zinc-500">INFERENCE_LATENCY</div>
                                    <div className="text-sm font-bold text-white mt-0.5">0.025 ms</div>
                                </div>
                                <div className="p-1.5 bg-zinc-950 border border-zinc-850">
                                    <div className="text-zinc-500">MODEL_TYPE</div>
                                    <div className="text-sm font-bold text-emerald-400 mt-0.5">RF_BALANCED</div>
                                </div>
                            </div>

                            <div className="p-1.5 bg-zinc-950 border border-zinc-850 space-y-1 text-[10px]">
                                <div className="text-zinc-500 text-[9px] font-bold">ROLLING_FEATURES_W5:</div>
                                <div className="flex justify-between text-zinc-300">
                                    <span>FEAT_DELTA_U (Δu):</span>
                                    <span className="text-amber-400">+3.8%/s</span>
                                </div>
                                <div className="flex justify-between text-zinc-300">
                                    <span>FEAT_UTIL_MEAN (u_mean):</span>
                                    <span>{metrics.peakUtil}%</span>
                                </div>
                                <div className="flex justify-between text-zinc-300">
                                    <span>FEAT_DELAY_MEAN (d_mean):</span>
                                    <span>{metrics.avgRtt}ms</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* ROUTING_EVENTS */}
                    <div className="border border-zinc-800 bg-zinc-900/60 p-2.5 text-xs">
                        <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-zinc-800 text-[11px]">
                            <span className="font-bold text-zinc-200">ROUTING_EVENTS // MBB_LOG</span>
                            <span className="text-zinc-500">ANTI_FLAP:δ15%</span>
                        </div>

                        <div className="space-y-1.5 max-h-56 overflow-y-auto text-[10px]">
                            {decisionLogs.map((log) => (
                                <div key={log.id} className="p-1.5 bg-zinc-950 border border-zinc-850 space-y-0.5">
                                    <div className="flex items-center justify-between">
                                        <span className={`px-1 text-[9px] font-bold ${
                                            log.type === 'REROUTE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                                            log.type === 'ANTI_FLAP' ? 'bg-amber-950 text-amber-400 border border-amber-800' : 'bg-zinc-800 text-zinc-400'
                                        }`}>
                                            {log.type}
                                        </span>
                                        <span className="text-zinc-500">{log.timestamp}</span>
                                    </div>
                                    <div className="text-zinc-300 leading-snug">{log.detail}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                </div>
            </div>

            {/* SECTION: BOTTOM_TABLES_AND_CONSOLE */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-2.5 font-mono">
                
                {/* FLOW_TABLE */}
                <div className="lg:col-span-8 border border-zinc-800 bg-zinc-900/60 p-2.5">
                    <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-zinc-800 text-[11px]">
                        <span className="font-bold text-zinc-200">FLOW_TABLE_OF13</span>
                        <div className="flex items-center gap-1 text-[10px]">
                            <span className="text-zinc-500">DPID:</span>
                            {['ALL', 's1', 's2', 's3', 's4', 's6'].map(sw => (
                                <button
                                    key={sw}
                                    onClick={() => setSelectedSwitch(sw)}
                                    className={`px-1.5 py-0.2 border ${
                                        selectedSwitch === sw ? 'border-emerald-500 bg-emerald-950 text-emerald-400' : 'border-zinc-800 bg-zinc-950 text-zinc-400'
                                    }`}
                                >
                                    {sw}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="overflow-x-auto max-h-48 text-[10px]">
                        <table className="w-full text-left divide-y divide-zinc-800">
                            <thead className="bg-zinc-950 text-zinc-500 uppercase sticky top-0">
                                <tr>
                                    <th className="py-1 px-1.5">FLOW_ID</th>
                                    <th className="py-1 px-1.5">DPID</th>
                                    <th className="py-1 px-1.5">PRIO</th>
                                    <th className="py-1 px-1.5">MATCH</th>
                                    <th className="py-1 px-1.5">ACTION</th>
                                    <th className="py-1 px-1.5 text-right">PKTS</th>
                                    <th className="py-1 px-1.5 text-right">BYTES</th>
                                    <th className="py-1 px-1.5 text-right">DUR</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-900 bg-zinc-950/40">
                                {filteredFlows.map((row) => (
                                    <tr key={row.id} className="hover:bg-zinc-900/60">
                                        <td className="py-1 px-1.5 font-bold text-white">{row.id}</td>
                                        <td className="py-1 px-1.5 text-emerald-400">{row.dpid}</td>
                                        <td className="py-1 px-1.5">{row.priority}</td>
                                        <td className="py-1 px-1.5 text-zinc-300">{row.match}</td>
                                        <td className="py-1 px-1.5 text-zinc-200">{row.action}</td>
                                        <td className="py-1 px-1.5 text-right text-zinc-400">{row.packetCount}</td>
                                        <td className="py-1 px-1.5 text-right text-zinc-300">{row.byteCount}</td>
                                        <td className="py-1 px-1.5 text-right text-zinc-500">{row.durationSec}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* CONTROLLER_STREAM */}
                <div className="lg:col-span-4 border border-zinc-800 bg-zinc-900/60 p-2.5 flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-zinc-800 text-[11px]">
                            <span className="font-bold text-zinc-200">CONTROLLER_STREAM</span>
                            <span className="text-zinc-500">PORT:6653</span>
                        </div>

                        <div className="bg-zinc-950 border border-zinc-850 p-1.5 text-[10px] text-zinc-400 h-28 overflow-y-auto space-y-0.5">
                            {consoleLogs.map((log, idx) => (
                                <div key={idx} className="leading-tight text-zinc-300 truncate">
                                    <span className="text-zinc-600">&gt;</span> {log}
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="mt-2 pt-1.5 border-t border-zinc-800">
                        <div className="text-[9px] font-bold text-zinc-500 mb-1">SCENARIO_PROFILES:</div>
                        <div className="grid grid-cols-3 gap-1 text-[9px]">
                            {SCENARIOS.map(sc => (
                                <button
                                    key={sc.id}
                                    onClick={() => handleSelectScenario(sc.id)}
                                    className={`p-1 border text-center truncate ${
                                        activeScenario === sc.id
                                            ? 'border-emerald-500 bg-emerald-950/60 text-emerald-300 font-bold'
                                            : 'border-zinc-800 bg-zinc-950 text-zinc-400 hover:border-zinc-700'
                                    }`}
                                >
                                    {sc.name}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

        </div>
    );
};

export default SDNDashboard;
