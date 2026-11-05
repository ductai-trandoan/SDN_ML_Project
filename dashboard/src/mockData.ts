/**
 * MOCK DATA & TYPE DEFINITIONS
 * Hệ thống giám sát QoS và điều phối lưu lượng mạng thích ứng dựa trên SDN và Machine Learning
 * Phản ánh chính xác topology 6 Open vSwitch (s1-s6), 4 Hosts, 3 đường song song P1-P3.
 */

export interface SystemMetrics {
    avgRtt: number;           // ms
    jitter: number;           // ms
    packetLoss: number;       // %
    peakUtil: number;         // %
    activeFlows: number;      // count
    rerouteTime: number;      // seconds
    controllerStatus: string;
    controllerRtt: number;    // ms
    mlStatus: string;
    mlInferenceMs: number;    // ms
    mlModel: string;
    mlF1: number;             // %
    activePath: 'P1' | 'P2' | 'P3';
    systemState: 'ADAPTIVE_STABLE' | 'CONGESTION_WARNING' | 'REROUTED_OPTIMAL';
    scenario: 'K1' | 'K2' | 'K3' | 'K4' | 'K5' | 'K6';
}

export interface LinkTelemetry {
    id: string;
    src: number;
    dst: number;
    path: 'P1' | 'P2' | 'P3';
    capacityMbps: number;
    throughputMbps: number;
    utilizationPct: number;
    delayMs: number;
    lossPct: number;
    status: 'NORMAL' | 'CONGESTED' | 'STANDBY' | 'DOWN';
}

export interface FlowEntry {
    id: string;
    dpid: string;
    priority: number;
    match: string;
    action: string;
    packetCount: number;
    byteCount: string;
    durationSec: string;
    status: 'ACTIVE' | 'BG_LOAD' | 'STANDBY' | 'DEFAULT';
}

export interface DecisionLog {
    id: number | string;
    timestamp: string;
    type: 'REROUTE' | 'ANTI_FLAP' | 'ML_INFER' | 'FLOW_MOD';
    flow: string;
    detail: string;
    status: 'SUCCESS' | 'HOLD' | 'WARN' | 'INFO';
}

export const INITIAL_METRICS: SystemMetrics = {
    avgRtt: 12.4,
    jitter: 1.18,
    packetLoss: 0.02,
    peakUtil: 76.5,
    activeFlows: 18,
    rerouteTime: 1.82,
    controllerStatus: 'ONLINE',
    controllerRtt: 1.8,
    mlStatus: 'ONLINE',
    mlInferenceMs: 0.025,
    mlModel: 'Random Forest (Balanced)',
    mlF1: 99.2,
    activePath: 'P1',
    systemState: 'ADAPTIVE_STABLE',
    scenario: 'K1'
};

export const INITIAL_LINKS: LinkTelemetry[] = [
    { id: 's1-s2', src: 1, dst: 2, path: 'P1', capacityMbps: 10, throughputMbps: 7.65, utilizationPct: 76.5, delayMs: 5.2, lossPct: 0.0, status: 'NORMAL' },
    { id: 's2-s6', src: 2, dst: 6, path: 'P1', capacityMbps: 10, throughputMbps: 7.65, utilizationPct: 76.5, delayMs: 5.4, lossPct: 0.0, status: 'NORMAL' },
    { id: 's1-s3', src: 1, dst: 3, path: 'P2', capacityMbps: 10, throughputMbps: 0.12, utilizationPct: 1.2, delayMs: 10.1, lossPct: 0.0, status: 'STANDBY' },
    { id: 's3-s4', src: 3, dst: 4, path: 'P2', capacityMbps: 10, throughputMbps: 0.12, utilizationPct: 1.2, delayMs: 10.0, lossPct: 0.0, status: 'STANDBY' },
    { id: 's4-s6', src: 4, dst: 6, path: 'P2', capacityMbps: 10, throughputMbps: 0.12, utilizationPct: 1.2, delayMs: 10.1, lossPct: 0.0, status: 'STANDBY' },
    { id: 's1-s5', src: 1, dst: 5, path: 'P3', capacityMbps: 5,  throughputMbps: 0.05, utilizationPct: 1.0, delayMs: 10.2, lossPct: 0.0, status: 'STANDBY' },
    { id: 's5-s6', src: 5, dst: 6, path: 'P3', capacityMbps: 5,  throughputMbps: 0.05, utilizationPct: 1.0, delayMs: 10.1, lossPct: 0.0, status: 'STANDBY' },
];

export const INITIAL_FLOWS: FlowEntry[] = [
    { id: 'fl-101', dpid: 's1', priority: 15, match: 'ip:10.0.0.1->10.0.0.2, tcp:5001', action: 'OUTPUT:port 2 (to s2)', packetCount: 14280, byteCount: '18.4 MB', durationSec: '48.2s', status: 'ACTIVE' },
    { id: 'fl-102', dpid: 's2', priority: 15, match: 'ip:10.0.0.1->10.0.0.2, tcp:5001', action: 'OUTPUT:port 2 (to s6)', packetCount: 14278, byteCount: '18.4 MB', durationSec: '48.2s', status: 'ACTIVE' },
    { id: 'fl-103', dpid: 's6', priority: 15, match: 'ip:10.0.0.1->10.0.0.2, tcp:5001', action: 'OUTPUT:port 1 (to h2)', packetCount: 14278, byteCount: '18.4 MB', durationSec: '48.2s', status: 'ACTIVE' },
    { id: 'fl-201', dpid: 's2', priority: 20, match: 'ip:10.0.0.3->10.0.0.4 (Cross)', action: 'OUTPUT:port 2 (to s6)', packetCount: 64120, byteCount: '82.0 MB', durationSec: '120.0s', status: 'BG_LOAD' },
    { id: 'fl-202', dpid: 's6', priority: 20, match: 'ip:10.0.0.3->10.0.0.4 (Cross)', action: 'OUTPUT:port 4 (to h4)', packetCount: 64120, byteCount: '82.0 MB', durationSec: '120.0s', status: 'BG_LOAD' },
    { id: 'fl-301', dpid: 's1', priority: 10, match: 'ip:10.0.0.1->10.0.0.2 [P2 Backup]', action: 'OUTPUT:port 3 (to s3)', packetCount: 120, byteCount: '154 KB', durationSec: '48.2s', status: 'STANDBY' },
    { id: 'fl-302', dpid: 's3', priority: 10, match: 'ip:10.0.0.1->10.0.0.2 [P2 Backup]', action: 'OUTPUT:port 2 (to s4)', packetCount: 120, byteCount: '154 KB', durationSec: '48.2s', status: 'STANDBY' },
    { id: 'fl-303', dpid: 's4', priority: 10, match: 'ip:10.0.0.1->10.0.0.2 [P2 Backup]', action: 'OUTPUT:port 2 (to s6)', packetCount: 120, byteCount: '154 KB', durationSec: '48.2s', status: 'STANDBY' },
    { id: 'fl-001', dpid: 's1', priority: 0,  match: '* (Table-miss wildcard)', action: 'CONTROLLER:OFPP_CONTROLLER', packetCount: 48, byteCount: '3.2 KB', durationSec: '360.0s', status: 'DEFAULT' },
];

export const INITIAL_DECISION_LOGS: DecisionLog[] = [
    { id: 1, timestamp: '13:58:12.410', type: 'REROUTE', flow: 'h1->h2', detail: 'Steered from P1 [s1-s2-s6] to P2 [s1-s3-s4-s6]. Link s2-s6 predicted util > 84% in H=5s. Cost: 2.41 -> 1.78 (-26.1%).', status: 'SUCCESS' },
    { id: 2, timestamp: '13:55:04.180', type: 'ANTI_FLAP', flow: 'h1->h2', detail: 'Hold timer active (T_hold = 10s, remaining 4.2s). Suppressed premature oscillation.', status: 'HOLD' },
    { id: 3, timestamp: '13:50:20.920', type: 'ML_INFER', flow: 'telemetry_stream', detail: 'Early Congestion Risk at 88.4% on link (2->6). Feature Δu = +4.8%/s, u_mean = 78.2%.', status: 'WARN' },
    { id: 4, timestamp: '13:48:00.000', type: 'FLOW_MOD', flow: 'h1->h2', detail: 'Installed baseline rules for P1 with priority 10. Make-Before-Break initialized.', status: 'INFO' }
];

export const SCENARIOS = [
    { id: 'K1', name: 'K1: Normal Load (2 Mbps)' },
    { id: 'K2', name: 'K2: Ramp Up (2->12 Mbps)' },
    { id: 'K3', name: 'K3: Burst Spike (14 Mbps)' },
    { id: 'K4', name: 'K4: Bottleneck Link (s2-s6)' },
    { id: 'K5', name: 'K5: Degraded (tc netem +50ms)' },
    { id: 'K6', name: 'K6: Link Failure (Failover)' },
];

