import 'package:flutter/material.dart';

import '../models/homelab_alerts.dart';
import '../services/homelab_service.dart';

class HomelabAlertsPanel extends StatefulWidget {
  const HomelabAlertsPanel({super.key});

  @override
  State<HomelabAlertsPanel> createState() => _HomelabAlertsPanelState();
}

class _HomelabAlertsPanelState extends State<HomelabAlertsPanel> {
  final HomelabService _service = HomelabService();
  late Future<HomelabAlertSummary> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchAlerts();
  }

  Future<void> _refresh() async {
    final next = _service.fetchAlerts();
    setState(() {
      _future = next;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<HomelabAlertSummary>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Center(child: CircularProgressIndicator()),
            ),
          );
        }
        if (!snapshot.hasData) {
          return Card(
            child: ListTile(
              leading: const Icon(Icons.warning_amber_rounded),
              title: const Text('Alerts unavailable'),
              trailing: IconButton(
                onPressed: _refresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ),
          );
        }

        final summary = snapshot.data!;
        final scheme = Theme.of(context).colorScheme;
        final healthy = summary.alerts.isEmpty;
        final statusColor = summary.criticalCount > 0
            ? scheme.error
            : summary.warningCount > 0
                ? Colors.orange
                : scheme.primary;

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      healthy ? Icons.check_circle_rounded : Icons.warning_rounded,
                      color: statusColor,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        healthy ? 'No active alerts' : 'Homelab alerts',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    if (!healthy)
                      Text(
                        '${summary.criticalCount} critical · ${summary.warningCount} warning',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    IconButton(
                      onPressed: _refresh,
                      tooltip: 'Refresh alerts',
                      icon: const Icon(Icons.refresh_rounded),
                    ),
                  ],
                ),
                if (healthy) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Host resources and Docker containers are within configured thresholds.',
                    style: TextStyle(color: scheme.onSurfaceVariant),
                  ),
                ] else ...[
                  const SizedBox(height: 8),
                  ...summary.alerts.map(
                    (alert) => Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(top: 10),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: (alert.isCritical ? scheme.error : Colors.orange)
                            .withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            alert.title,
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 3),
                          Text('${alert.source} · ${alert.message}'),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
