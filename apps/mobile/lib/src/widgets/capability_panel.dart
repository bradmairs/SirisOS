import 'package:flutter/material.dart';

import '../core/capability_registry.dart';
import '../core/siris_connector.dart';
import 'context_panel.dart';
import 'siris_design_system.dart';

class CapabilityPanel extends StatelessWidget {
  const CapabilityPanel({required this.health, super.key});

  final Map<String, SirisConnectorHealth> health;

  @override
  Widget build(BuildContext context) {
    final statuses = SirisCapabilityRegistry.instance.statuses(health: health);
    final available = statuses.where((item) => item.available).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const ContextPanel(),
        const SizedBox(height: 18),
        SirisPanel(
          title: 'Capabilities',
          subtitle: '$available/${statuses.length} currently available',
          icon: Icons.extension_rounded,
          child: Column(
            children: statuses.map((item) {
              final capability = item.capability;
              final status = item.available ? SirisStatus.success : SirisStatus.neutral;
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            capability.title,
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${capability.id} · ${capability.providerId}',
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                          const SizedBox(height: 3),
                          Text(
                            item.reason,
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                          ),
                          if (capability.requiresConfirmation) ...[
                            const SizedBox(height: 3),
                            Text(
                              'Confirmation required · ${capability.risk.name} risk',
                              style: Theme.of(context).textTheme.labelSmall,
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    SirisStatusChip(
                      label: item.available ? 'AVAILABLE' : 'UNAVAILABLE',
                      status: status,
                    ),
                  ],
                ),
              );
            }).toList(growable: false),
          ),
        ),
      ],
    );
  }
}
