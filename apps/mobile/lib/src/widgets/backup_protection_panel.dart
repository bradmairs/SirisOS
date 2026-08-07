import 'package:flutter/material.dart';

import '../models/backup_protection.dart';
import '../services/history_service.dart';
import 'siris_design_system.dart';

class BackupProtectionPanel extends StatefulWidget {
  const BackupProtectionPanel({super.key});

  @override
  State<BackupProtectionPanel> createState() => _BackupProtectionPanelState();
}

class _BackupProtectionPanelState extends State<BackupProtectionPanel> {
  final HistoryService _service = HistoryService();
  late Future<BackupProtectionSummary> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchBackupProtection();
  }

  void _refresh() => setState(() => _future = _service.fetchBackupProtection());

  @override
  Widget build(BuildContext context) => SirisPanel(
        title: 'Backup protection',
        subtitle: 'Completed Hyper Backup runs over the last 30 days',
        icon: Icons.shield_rounded,
        child: FutureBuilder<BackupProtectionSummary>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 18),
                child: LinearProgressIndicator(),
              );
            }
            if (snapshot.hasError) {
              return Row(
                children: [
                  const Expanded(child: Text('Backup analytics are temporarily unavailable.')),
                  IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh_rounded)),
                ],
              );
            }
            final data = snapshot.data;
            if (data == null || data.completions == 0) {
              return const Text(
                'No completed backup runs have been observed yet. Analytics will populate as Hyper Backup completes jobs.',
              );
            }
            final rate = data.successRatePercent;
            final status = data.failures == 0 ? SirisStatus.success : SirisStatus.warning;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 28,
                  runSpacing: 16,
                  children: [
                    SirisMetric(
                      label: 'Success rate',
                      value: rate == null ? '—' : '${rate.toStringAsFixed(1)}%',
                      icon: Icons.verified_rounded,
                    ),
                    SirisMetric(
                      label: 'Completed',
                      value: '${data.completions}',
                      detail: '${data.failures} failed',
                      icon: Icons.backup_rounded,
                    ),
                    SirisMetric(
                      label: 'Tasks',
                      value: '${data.tasks.length}',
                      icon: Icons.checklist_rounded,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SirisStatusChip(
                  label: data.failures == 0 ? 'PROTECTED' : 'ATTENTION',
                  status: status,
                ),
                if (data.tasks.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  for (final task in data.tasks.take(4))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              task.taskName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Text(
                            task.successRatePercent == null
                                ? '—'
                                : '${task.successRatePercent!.toStringAsFixed(0)}%',
                          ),
                        ],
                      ),
                    ),
                ],
              ],
            );
          },
        ),
      );
}
