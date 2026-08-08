import 'dart:async';

import 'package:flutter/material.dart';

import '../core/siris_context_service.dart';
import '../core/siris_event_bus.dart';
import 'siris_design_system.dart';

class ContextPanel extends StatefulWidget {
  const ContextPanel({super.key});

  @override
  State<ContextPanel> createState() => _ContextPanelState();
}

class _ContextPanelState extends State<ContextPanel> {
  StreamSubscription<SirisEvent>? _events;

  @override
  void initState() {
    super.initState();
    _events = SirisEventBus.instance.on<ContextSnapshotChanged>().listen((_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _events?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final service = SirisCoreContextService.instance;
    final snapshot = service.snapshot;
    final primary = snapshot.primary;
    final timeline = service.timeline.take(5).toList(growable: false);

    return SirisPanel(
      title: 'Current context',
      subtitle: primary == null
          ? 'Context providers are still initializing.'
          : 'Primary: ${primary.label}',
      icon: Icons.psychology_alt_rounded,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (snapshot.facts.isEmpty)
            const Text('No active context facts yet.')
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: snapshot.facts
                  .map(
                    (fact) => SirisStatusChip(
                      label: fact.label,
                      status: fact.priority >= 90
                          ? SirisStatus.critical
                          : fact.priority >= 70
                              ? SirisStatus.warning
                              : SirisStatus.success,
                    ),
                  )
                  .toList(growable: false),
            ),
          if (timeline.isNotEmpty) ...[
            const SizedBox(height: 18),
            Text('Recent context changes', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            for (final entry in timeline)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    Icon(
                      entry.active ? Icons.add_circle_outline_rounded : Icons.remove_circle_outline_rounded,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${entry.active ? 'Entered' : 'Cleared'} ${entry.label}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    Text(
                      _formatTime(entry.occurredAt),
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

String _formatTime(DateTime value) {
  final local = value.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}
