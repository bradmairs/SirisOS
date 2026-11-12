import { api } from "./client";

export interface Disk { label: string; path: string; total_gb: number; free_gb: number; used_percent: number }
export interface GpuModel { name: string; size_gb: number; vram_gb: number; ram_gb: number; on_gpu_percent: number }
export interface Machine {
  checked: string; disks: Disk[]; warn_percent: number; alert_percent: number;
  ollama: { configured: boolean; models: GpuModel[]; error: string | null };
}

/** The server's disks and what the local AI has on the GPU (8.9). */
export const machine = { get: (fresh = false) => api<Machine>(`/api/v1/machine${fresh ? "?fresh=1" : ""}`) };
