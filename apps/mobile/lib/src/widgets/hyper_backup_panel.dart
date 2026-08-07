import 'package:flutter/material.dart';

import '../models/synology_snapshot.dart';
import '../services/synology_service.dart';
import 'siris_design_system.dart';

class HyperBackupPanel extends StatefulWidget {
  const HyperBackupPanel({super.key});

  @override
  State<HyperBackupPanel> createState() => _HyperBackupPanelState();
}

class _HyperBackupPanelState extends State<HyperBackupPanel> {
  final SynologyService _service = SynologyService();
  late final Future<SynologySnapshot> _future = _service.fetchSnapshot();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SynologySnapshot>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SirisPanel(
            title: 'Hyper Backup',
            icon: Icons.backup_rounded,
            child: LinearProgressIndicator(),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const SirisPanel(
            title: 'Hyper Backup',
            icon: Icons.backup_rounded,
            child: Text('Backup status unavailable.'),
          );
        }

        final data = snapshot.data!;
        if (!data.configured) {
          return const SirisPanel(
            title: 'Hyper Backup',
            subtitle: 'Synology integration required',
            icon: Icons.backup_rounded,
            child: Text('Configure the Synology DSM connector to monitor backups.'),
          );
        }
        if (!data.backupApiAvailable) {
          return const SirisPanel(
            title: 'Hyper Backup',
            subtitle: 'Capability not detected',
            icon: Icons.backup_rounded,
            child: Text('DSM did not expose SYNO.Backup.Task to this account.'),
          );
        }

        final status = !data.available || data.failedBackupTasks > 0
            ? SirisStatus.critical
            : data.runningBackupTasks > 0
                ? SirisStatus.info
                : SirisStatus.success;
        final label = data.failedBackupTasks > 0
            ? '${data.failedBackupTasks} failed'
            : data.runningBackupTasks > 0
                ? '${data.runningBackupTasks} running'
                : 'Protected';
        final recent = data.backupTasks.take(3).toList(growable: false);

        return SirisPanel(
          title: 'Hyper Backup',
          subtitle: '${data.backupTasks.length} task${data.backupTasks.length == 1 ? '' : 's'}',
          icon: Icons.backup_rounded,
          trailing: SirisStatusChip(label: label, status: status),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 28,
                runSpacing: 16,
                children: [
                  SirisMetric(label: 'Tasks', value: '${data.backupTasks.length}'),
                  SirisMetric(label: 'Running', value: '${data.runningBackupTasks}'),
                  SirisMetric(label: 'Failed', value: '${data.failedBackupTasks}'),
                ],
              ),
              if (recent.isNotEmpty) ...[
                const SizedBox(height: 18),
                ...recent.map((task) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          Icon(
                            task.failed
                                ? Icons.error_rounded
                                : task.running
                                    ? Icons.sync_rounded
                                    : Icons.check_circle_rounded,
                            size: 16,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              task.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(task.lastResult ?? task.state),
                        ],
                      ),
                    )),
              ],
            ],
          ),
        );
      },
    );
  }
}
