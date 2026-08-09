import 'package:flutter/material.dart';

import '../models/activity_event.dart';
import '../services/activity_service.dart';

class ActivityFeedPanel extends StatefulWidget {
  const ActivityFeedPanel({super.key});

  @override
  State<ActivityFeedPanel> createState() => _ActivityFeedPanelState();
}

class _ActivityFeedPanelState extends State<ActivityFeedPanel> {
  final ActivityService _service = ActivityService();
  late Future<List<ActivityEvent>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchEvents(limit: 8);
  }

  Future<void> _refresh() async {
    final next = _service.fetchEvents(limit: 8);
    setState(() {
      _future = next;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.notifications_rounded,
                    color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('Recent activity',
                      style: Theme.of(context).textTheme.titleLarge),
                ),
                IconButton(
                  onPressed: _refresh,
                  tooltip: 'Refresh activity',
                  icon: const Icon(Icons.refresh_rounded),
                ),
              ],
            ),
            const SizedBox(height: 12),
            FutureBuilder<List<ActivityEvent>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snapshot.hasError) {
                  return Text('Activity is temporarily unavailable.',
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error));
                }
                final events = snapshot.data ?? const <ActivityEvent>[];
                if (events.isEmpty) {
                  return Text(
                    'No activity yet. New runs, workouts and system actions will appear here.',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  );
                }
                return Column(
                  children: events
                      .map((event) => _ActivityRow(event: event))
                      .toList(growable: false),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ActivityRow extends StatelessWidget {
  const _ActivityRow({required this.event});

  final ActivityEvent event;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = switch (event.severity) {
      'critical' => scheme.error,
      'warning' => scheme.tertiary,
      'success' => scheme.primary,
      _ => scheme.onSurfaceVariant,
    };
    final icon = switch (event.module) {
      'running' => Icons.directions_run_rounded,
      'gym' => Icons.fitness_center_rounded,
      'homelab' => Icons.dns_rounded,
      _ => Icons.bolt_rounded,
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: color.withValues(alpha: 0.14),
            child: Icon(icon, size: 18, color: color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(event.title,
                    style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 3),
                Text(event.message),
                const SizedBox(height: 3),
                Text(
                  _timeLabel(context, event.occurredAt),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _timeLabel(BuildContext context, DateTime value) {
    final local = value.toLocal();
    final now = DateTime.now();
    final sameDay = local.year == now.year &&
        local.month == now.month &&
        local.day == now.day;
    if (sameDay) return TimeOfDay.fromDateTime(local).format(context);
    return '${local.day}/${local.month} ${TimeOfDay.fromDateTime(local).format(context)}';
  }
}
