import 'package:flutter/material.dart';

import '../models/homelab_audit_event.dart';
import '../services/homelab_service.dart';

class HomelabActivityScreen extends StatefulWidget {
  const HomelabActivityScreen({super.key});

  @override
  State<HomelabActivityScreen> createState() => _HomelabActivityScreenState();
}

class _HomelabActivityScreenState extends State<HomelabActivityScreen> {
  final HomelabService _service = HomelabService();
  late Future<List<HomelabAuditEvent>> _future;

  @override
  void initState() {
    super.initState();
    _future = _service.fetchAuditHistory();
  }

  Future<void> _refresh() async {
    final next = _service.fetchAuditHistory();
    setState(() => _future = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Homelab activity'),
        actions: [
          IconButton(
            onPressed: _refresh,
            tooltip: 'Refresh activity',
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: FutureBuilder<List<HomelabAuditEvent>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: FilledButton.icon(
                onPressed: _refresh,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Retry activity'),
              ),
            );
          }
          final events = snapshot.data ?? const <HomelabAuditEvent>[];
          if (events.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text(
                  'No container actions have been recorded yet.',
                  textAlign: TextAlign.center,
                ),
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.separated(
              padding: const EdgeInsets.all(20),
              itemCount: events.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) => _ActivityCard(event: events[index]),
            ),
          );
        },
      ),
    );
  }
}

class _ActivityCard extends StatelessWidget {
  const _ActivityCard({required this.event});

  final HomelabAuditEvent event;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isSuccess = event.result == 'success';
    final isBlocked = event.result == 'blocked';
    final color = isSuccess
        ? scheme.primary
        : isBlocked
            ? scheme.tertiary
            : scheme.error;
    final icon = isSuccess
        ? Icons.check_circle_rounded
        : isBlocked
            ? Icons.shield_rounded
            : Icons.error_rounded;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
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
                  Text(
                    '${event.action.toUpperCase()} · ${event.targetLabel}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '${event.result} by ${event.username}',
                    style: TextStyle(color: color, fontWeight: FontWeight.w600),
                  ),
                  if (event.detail != null && event.detail!.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(event.detail!),
                  ],
                  const SizedBox(height: 8),
                  Text(
                    event.occurredAt.toLocal().toString(),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
