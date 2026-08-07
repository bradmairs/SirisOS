import 'package:flutter/material.dart';

import '../models/storage_snapshot.dart';
import '../services/storage_service.dart';
import 'siris_design_system.dart';

class StoragePanel extends StatefulWidget {
  const StoragePanel({super.key});

  @override
  State<StoragePanel> createState() => _StoragePanelState();
}

class _StoragePanelState extends State<StoragePanel> {
  final StorageService _service = StorageService();
  late final Future<StorageSnapshot> _future = _service.fetchSnapshot();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<StorageSnapshot>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SirisPanel(
            title: 'Storage',
            icon: Icons.storage_rounded,
            child: LinearProgressIndicator(),
          );
        }
        if (snapshot.hasError || !snapshot.hasData) {
          return const SirisPanel(
            title: 'Storage',
            icon: Icons.storage_rounded,
            child: Text('Storage status unavailable.'),
          );
        }

        final data = snapshot.data!;
        if (!data.available) {
          return SirisPanel(
            title: 'Storage',
            icon: Icons.storage_rounded,
            trailing: const SirisStatusChip(
              label: 'Unavailable',
              status: SirisStatus.critical,
            ),
            child: Text(data.error ?? 'Storage monitoring unavailable.'),
          );
        }

        final highest = data.highestUsedPercent ?? 0;
        final status = highest >= 95
            ? SirisStatus.critical
            : highest >= 85
                ? SirisStatus.warning
                : SirisStatus.success;
        final topVolume = data.volumes.isEmpty ? null : data.volumes.first;

        return SirisPanel(
          title: 'Storage',
          subtitle: 'Host filesystems',
          icon: Icons.storage_rounded,
          trailing: SirisStatusChip(
            label: '${highest.toStringAsFixed(0)}% peak',
            status: status,
          ),
          child: Wrap(
            spacing: 28,
            runSpacing: 16,
            children: [
              SirisMetric(label: 'Volumes', value: '${data.volumes.length}'),
              SirisMetric(
                label: 'Used',
                value: _formatBytes(data.usedBytes),
              ),
              SirisMetric(
                label: 'Free',
                value: _formatBytes(data.availableBytes),
              ),
              if (topVolume != null)
                SirisMetric(
                  label: topVolume.mountpoint,
                  value: '${topVolume.usedPercent.toStringAsFixed(0)}%',
                ),
            ],
          ),
        );
      },
    );
  }

  static String _formatBytes(int bytes) {
    const gib = 1024 * 1024 * 1024;
    const tib = gib * 1024;
    if (bytes >= tib) return '${(bytes / tib).toStringAsFixed(1)} TB';
    return '${(bytes / gib).toStringAsFixed(1)} GB';
  }
}
