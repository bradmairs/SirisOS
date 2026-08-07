import 'package:flutter/material.dart';

import '../models/synology_snapshot.dart';
import '../services/synology_service.dart';
import 'siris_design_system.dart';

class SynologyPanel extends StatelessWidget {
  const SynologyPanel({super.key});
  static final SynologyService _service = SynologyService();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SynologySnapshot>(
      future: _service.fetchSnapshot(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SirisPanel(
            title: 'Synology',
            icon: Icons.storage_rounded,
            child: LinearProgressIndicator(),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const SirisPanel(
            title: 'Synology',
            icon: Icons.storage_rounded,
            child: Text('Synology status unavailable.'),
          );
        }

        final data = snapshot.data!;
        if (!data.configured) {
          return const SirisPanel(
            title: 'Synology',
            subtitle: 'Optional integration',
            icon: Icons.storage_rounded,
            child: Text('Configure SYNOLOGY_URL, SYNOLOGY_USERNAME and SYNOLOGY_PASSWORD.'),
          );
        }

        final issues = data.unhealthyDisks + data.unhealthyVolumes;
        final status = !data.available
            ? SirisStatus.critical
            : issues > 0
                ? SirisStatus.critical
                : (data.highestUsedPercent ?? 0) >= 85
                    ? SirisStatus.warning
                    : SirisStatus.success;
        final label = !data.available
            ? 'Unavailable'
            : issues > 0
                ? '$issues issue${issues == 1 ? '' : 's'}'
                : 'Healthy';

        return SirisPanel(
          title: data.model ?? 'Synology',
          subtitle: data.dsmVersion ?? 'DSM',
          icon: Icons.storage_rounded,
          trailing: SirisStatusChip(label: label, status: status),
          child: Wrap(
            spacing: 28,
            runSpacing: 16,
            children: [
              SirisMetric(label: 'Volumes', value: '${data.volumes.length}'),
              SirisMetric(label: 'Disks', value: '${data.disks.length}'),
              SirisMetric(
                label: 'Peak use',
                value: data.highestUsedPercent == null
                    ? '—'
                    : '${data.highestUsedPercent!.toStringAsFixed(0)}%',
              ),
              SirisMetric(
                label: 'Backup API',
                value: data.backupApiAvailable ? 'Detected' : 'Not detected',
              ),
            ],
          ),
        );
      },
    );
  }
}
