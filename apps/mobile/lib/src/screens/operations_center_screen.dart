import 'dart:async';

import 'package:flutter/material.dart';

import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../core/siris_integration_manager.dart';
import '../widgets/siris_design_system.dart';

class OperationsCenterScreen extends StatefulWidget {
  const OperationsCenterScreen({super.key});

  static const routeName = '/operations';

  @override
  State<OperationsCenterScreen> createState() => _OperationsCenterScreenState();
}

class _OperationsCenterScreenState extends State<OperationsCenterScreen> {
  StreamSubscription<SirisEvent>? _events;

  @override
  void initState() {
    super.initState();
    _events = SirisEventBus.instance.events.listen((event) {
      if (event is IntegrationHealthChanged ||
          event is NotificationPolicyStateChanged ||
          event is NotificationStateChanged) {
        if (mounted) setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _events?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final policies = NotificationPolicyEngine.instance.activeOutcomes.toList()
      ..sort((a, b) => _severityRank(b.severity).compareTo(_severityRank(a.severity)));
    final manager = SirisIntegrationManager.instance;
    final connectors = manager.connectors.toList(growable: false);
    final health = manager.health;
    final attentionCount = policies.length +
        health.values.where((value) => value.hasError).length;
    final criticalCount = policies.where((item) => item.isCritical).length +
        health.values.where((value) => value.state == SirisConnectorState.failed).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Operations Center'),
        actions: [
          IconButton(
            tooltip: 'Refresh integrations',
            onPressed: () async {
              await Future.wait(
                connectors.map((connector) => manager.refresh(connector.id)),
              );
              if (mounted) setState(() {});
            },
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 1000;
            return ListView(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
              children: [
                _Overview(
                  attentionCount: attentionCount,
                  criticalCount: criticalCount,
                  healthyCount: health.values.where((value) => value.isHealthy).length,
                  integrationCount: connectors.length,
                ),
                const SizedBox(height: 18),
                if (wide)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: _IncidentPanel(policies: policies)),
                      const SizedBox(width: 18),
                      Expanded(
                        child: _IntegrationPanel(
                          connectors: connectors,
                          health: health,
                        ),
                      ),
                    ],
                  )
                else ...[
                  _IncidentPanel(policies: policies),
                  const SizedBox(height: 18),
                  _IntegrationPanel(connectors: connectors, health: health),
                ],
                const SizedBox(height: 18),
                _AttentionPanel(policies: policies, health: health),
              ],
            );
          },
        ),
      ),
    );
  }

  static int _severityRank(NotificationPolicySeverity severity) => switch (severity) {
        NotificationPolicySeverity.info => 1,
        NotificationPolicySeverity.warning => 2,
        NotificationPolicySeverity.critical => 3,
      };
}

class _Overview extends StatelessWidget {
  const _Overview({
    required this.attentionCount,
    required this.criticalCount,
    required this.healthyCount,
    required this.integrationCount,
  });

  final int attentionCount;
  final int criticalCount;
  final int healthyCount;
  final int integrationCount;

  @override
  Widget build(BuildContext context) => SirisPanel(
        title: 'Operational overview',
        subtitle: attentionCount == 0
            ? 'No active issues require attention.'
            : '$attentionCount active item${attentionCount == 1 ? '' : 's'} require attention.',
        icon: Icons.radar_rounded,
        accent: criticalCount > 0 ? Theme.of(context).colorScheme.error : null,
        child: Wrap(
          spacing: 30,
          runSpacing: 18,
          children: [
            SirisMetric(
              label: 'Attention',
              value: '$attentionCount',
              icon: Icons.notifications_active_rounded,
            ),
            SirisMetric(
              label: 'Critical',
              value: '$criticalCount',
              icon: Icons.error_rounded,
            ),
            SirisMetric(
              label: 'Healthy',
              value: '$healthyCount/$integrationCount',
              detail: 'integrations',
              icon: Icons.check_circle_rounded,
            ),
          ],
        ),
      );
}

class _IncidentPanel extends StatelessWidget {
  const _IncidentPanel({required this.policies});

  final List<NotificationPolicyOutcome> policies;

  @override
  Widget build(BuildContext context) => SirisPanel(
        title: 'Active incidents',
        subtitle: 'Deterministic Notification Policy outcomes',
        icon: Icons.warning_amber_rounded,
        child: policies.isEmpty
            ? const _EmptyState(
                icon: Icons.verified_rounded,
                title: 'No active incidents',
                message: 'All active policy conditions are currently clear.',
              )
            : Column(
                children: policies
                    .map((outcome) => _IncidentRow(outcome: outcome))
                    .toList(growable: false),
              ),
      );
}

class _IncidentRow extends StatelessWidget {
  const _IncidentRow({required this.outcome});

  final NotificationPolicyOutcome outcome;

  @override
  Widget build(BuildContext context) {
    final status = switch (outcome.severity) {
      NotificationPolicySeverity.info => SirisStatus.info,
      NotificationPolicySeverity.warning => SirisStatus.warning,
      NotificationPolicySeverity.critical => SirisStatus.critical,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(
              outcome.isCritical ? Icons.error_rounded : Icons.warning_amber_rounded,
              size: 19,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(outcome.rule.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(
                  outcome.rule.message,
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 5),
                Text(
                  '${outcome.moduleId} · active since ${_formatDateTime(outcome.activatedAt)}',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          SirisStatusChip(label: outcome.severity.name.toUpperCase(), status: status),
        ],
      ),
    );
  }
}

class _IntegrationPanel extends StatelessWidget {
  const _IntegrationPanel({required this.connectors, required this.health});

  final List<SirisConnector> connectors;
  final Map<String, SirisConnectorHealth> health;

  @override
  Widget build(BuildContext context) => SirisPanel(
        title: 'Integrations',
        subtitle: 'Live Integration Manager state',
        icon: Icons.hub_rounded,
        child: connectors.isEmpty
            ? const _EmptyState(
                icon: Icons.hub_outlined,
                title: 'No integrations registered',
                message: 'Integration startup may still be in progress.',
              )
            : Column(
                children: connectors.map((connector) {
                  final item = health[connector.id];
                  return _IntegrationRow(connector: connector, health: item);
                }).toList(growable: false),
              ),
      );
}

class _IntegrationRow extends StatelessWidget {
  const _IntegrationRow({required this.connector, required this.health});

  final SirisConnector connector;
  final SirisConnectorHealth? health;

  @override
  Widget build(BuildContext context) {
    final state = health?.state ?? SirisConnectorState.disconnected;
    final status = switch (state) {
      SirisConnectorState.healthy => SirisStatus.success,
      SirisConnectorState.connecting => SirisStatus.info,
      SirisConnectorState.degraded => SirisStatus.warning,
      SirisConnectorState.failed => SirisStatus.critical,
      SirisConnectorState.disabled || SirisConnectorState.disconnected => SirisStatus.neutral,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(connector.label, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(
                  health?.message ?? 'Disconnected',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          SirisStatusChip(label: state.name.toUpperCase(), status: status),
        ],
      ),
    );
  }
}

class _AttentionPanel extends StatelessWidget {
  const _AttentionPanel({required this.policies, required this.health});

  final List<NotificationPolicyOutcome> policies;
  final Map<String, SirisConnectorHealth> health;

  @override
  Widget build(BuildContext context) {
    final failed = health.entries.where((entry) => entry.value.hasError).toList(growable: false);
    return SirisPanel(
      title: 'What needs attention',
      subtitle: 'Prioritised operational work queue',
      icon: Icons.task_alt_rounded,
      child: policies.isEmpty && failed.isEmpty
          ? const _EmptyState(
              icon: Icons.done_all_rounded,
              title: 'Nothing pending',
              message: 'SirisOS has no active operational work items.',
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final policy in policies)
                  _AttentionRow(
                    icon: policy.isCritical ? Icons.priority_high_rounded : Icons.warning_rounded,
                    title: policy.rule.title,
                    detail: policy.rule.message,
                  ),
                for (final entry in failed)
                  _AttentionRow(
                    icon: Icons.link_off_rounded,
                    title: '${entry.key} integration ${entry.value.state.name}',
                    detail: entry.value.message,
                  ),
              ],
            ),
    );
  }
}

class _AttentionRow extends StatelessWidget {
  const _AttentionRow({required this.icon, required this.title, required this.detail});

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(
                    detail,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.icon, required this.title, required this.message});

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            Icon(icon, size: 30),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(
                    message,
                    style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
}

String _formatDateTime(DateTime value) {
  final local = value.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '${local.day}/${local.month} $hour:$minute';
}
