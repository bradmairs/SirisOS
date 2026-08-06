import 'package:flutter/material.dart';

import '../models/activity_event.dart';
import '../services/activity_service.dart';

class NotificationCenterScreen extends StatefulWidget {
  const NotificationCenterScreen({super.key});

  @override
  State<NotificationCenterScreen> createState() => _NotificationCenterScreenState();
}

class _NotificationCenterScreenState extends State<NotificationCenterScreen> {
  final ActivityService _service = ActivityService();
  String _severity = 'all';
  bool _loading = true;
  bool _markingRead = false;
  String? _error;
  List<ActivityEvent> _events = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final events = await _service.fetchEvents(limit: 100, severity: _severity);
      if (mounted) setState(() => _events = events);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _markAllRead() async {
    if (_markingRead) return;
    setState(() => _markingRead = true);
    try {
      await _service.markAllRead();
      await _load();
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not mark notifications as read: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _markingRead = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          TextButton.icon(
            onPressed: _markingRead ? null : _markAllRead,
            icon: _markingRead
                ? const SizedBox.square(dimension: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.done_all_rounded),
            label: const Text('Read all'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final option in const ['all', 'warning', 'critical', 'success'])
                  ChoiceChip(
                    label: Text(option == 'all' ? 'All' : '${option[0].toUpperCase()}${option.substring(1)}'),
                    selected: _severity == option,
                    onSelected: (_) {
                      setState(() => _severity = option);
                      _load();
                    },
                  ),
              ],
            ),
            const SizedBox(height: 18),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 48),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null)
              _MessageCard(icon: Icons.cloud_off_rounded, message: _error!)
            else if (_events.isEmpty)
              const _MessageCard(icon: Icons.notifications_none_rounded, message: 'No notifications match this filter.')
            else
              ..._events.map((event) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _NotificationCard(event: event),
                  )),
          ],
        ),
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.event});
  final ActivityEvent event;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = switch (event.severity) {
      'critical' => scheme.error,
      'warning' => scheme.tertiary,
      'success' => scheme.primary,
      _ => scheme.secondary,
    };
    final icon = switch (event.module) {
      'homelab' => Icons.dns_rounded,
      'running' => Icons.directions_run_rounded,
      'gym' => Icons.fitness_center_rounded,
      _ => Icons.notifications_rounded,
    };
    final local = event.occurredAt.toLocal();
    final time = '${local.day}/${local.month}/${local.year} · ${TimeOfDay.fromDateTime(local).format(context)}';

    return Card(
      color: event.isUnread ? color.withValues(alpha: 0.10) : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(
              backgroundColor: color.withValues(alpha: 0.14),
              child: Icon(icon, color: color),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(event.title, style: Theme.of(context).textTheme.titleMedium)),
                      if (event.isUnread)
                        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(event.message),
                  const SizedBox(height: 8),
                  Text(time, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.icon, required this.message});
  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          children: [
            Icon(icon, size: 42, color: Theme.of(context).colorScheme.onSurfaceVariant),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
