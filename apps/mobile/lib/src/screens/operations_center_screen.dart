import 'dart:async';

import 'package:flutter/material.dart';

import '../core/dependency_graph.dart';
import '../core/incident_engine.dart';
import '../core/notification_policy.dart';
import '../core/siris_connector.dart';
import '../core/siris_event_bus.dart';
import '../core/siris_integration_manager.dart';
import '../services/action_service.dart';
import '../services/incident_lifecycle_service.dart';
import '../services/recommendation_service.dart';
import '../widgets/backup_protection_panel.dart';
import '../widgets/capability_panel.dart';
import '../widgets/dependency_graph_panel.dart';
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
    unawaited(
      DependencyGraph.instance.load().then((_) {
        if (mounted) setState(() {});
      }),
    );
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
      ..sort((a, b) =>
          _severityRank(b.severity).compareTo(_severityRank(a.severity)));
    final manager = SirisIntegrationManager.instance;
    final connectors = manager.connectors.toList(growable: false);
    final health = manager.health;
    final incidents = IncidentEngine.instance.correlate(
      outcomes: policies,
      integrationHealth: health,
    );
    final attentionCount = incidents.length +
        health.values.where((value) => value.hasError).length;
    final criticalCount = incidents.where((item) => item.isCritical).length +
        health.values
            .where((value) => value.state == SirisConnectorState.failed)
            .length;

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
                  healthyCount:
                      health.values.where((value) => value.isHealthy).length,
                  integrationCount: connectors.length,
                ),
                const SizedBox(height: 18),
                if (wide)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: _IncidentPanel(incidents: incidents)),
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
                  _IncidentPanel(incidents: incidents),
                  const SizedBox(height: 18),
                  _IntegrationPanel(connectors: connectors, health: health),
                ],
                const SizedBox(height: 18),
                const RepaintBoundary(child: _RecommendationsPanel()),
                const SizedBox(height: 18),
                _AttentionPanel(policies: policies, health: health),
                const SizedBox(height: 18),
                RepaintBoundary(child: CapabilityPanel(health: health)),
                const SizedBox(height: 18),
                RepaintBoundary(
                  child: DependencyGraphPanel(
                    onChanged: () {
                      if (mounted) setState(() {});
                    },
                  ),
                ),
                const SizedBox(height: 18),
                const RepaintBoundary(child: BackupProtectionPanel()),
              ],
            );
          },
        ),
      ),
    );
  }

  static int _severityRank(NotificationPolicySeverity severity) =>
      switch (severity) {
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

class _IncidentPanel extends StatefulWidget {
  const _IncidentPanel({required this.incidents});

  final List<SirisIncident> incidents;

  @override
  State<_IncidentPanel> createState() => _IncidentPanelState();
}

class _IncidentPanelState extends State<_IncidentPanel> {
  final _service = IncidentLifecycleService();
  late Future<List<IncidentLifecycleRecord>> _future;
  final Set<String> _busy = {};

  @override
  void initState() {
    super.initState();
    _future = _service.list();
  }

  void _refresh() {
    setState(() => _future = _service.list());
  }

  Future<void> _updateStatus(String incidentId, IncidentLifecycleStatus status) async {
    setState(() => _busy.add(incidentId));
    try {
      await _service.update(incidentId, status: status);
      _refresh();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to update incident.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy.remove(incidentId));
    }
  }

  @override
  Widget build(BuildContext context) => SirisPanel(
        title: 'Active incidents',
        subtitle: 'Correlated conditions with declared dependency impact',
        icon: Icons.warning_amber_rounded,
        child: FutureBuilder<List<IncidentLifecycleRecord>>(
          future: _future,
          builder: (context, snapshot) {
            // Lifecycle is enrichment on top of the live, always-correct
            // incident list -- a failed/slow lifecycle fetch must never hide
            // an active incident, so the live list still renders during
            // ConnectionState.waiting and even if this errors.
            final lifecycle = <String, IncidentLifecycleRecord>{
              for (final record in snapshot.data ?? const <IncidentLifecycleRecord>[])
                record.id: record,
            };
            final activeIds = widget.incidents.map((item) => item.id).toSet();
            final history = (snapshot.data ?? const <IncidentLifecycleRecord>[])
                .where((record) => record.status == IncidentLifecycleStatus.resolved && !activeIds.contains(record.id))
                .toList()
              ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (widget.incidents.isEmpty)
                  const _EmptyState(
                    icon: Icons.verified_rounded,
                    title: 'No active incidents',
                    message: 'All active policy conditions are currently clear.',
                  )
                else
                  Column(
                    children: widget.incidents
                        .map(
                          (incident) => _IncidentRow(
                            incident: incident,
                            lifecycle: lifecycle[incident.id],
                            busy: _busy.contains(incident.id),
                            onAcknowledge: () =>
                                _updateStatus(incident.id, IncidentLifecycleStatus.acknowledged),
                            onResolve: () => _updateStatus(incident.id, IncidentLifecycleStatus.resolved),
                            onReopen: () => _updateStatus(incident.id, IncidentLifecycleStatus.open),
                          ),
                        )
                        .toList(growable: false),
                  ),
                if (history.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text('Recently resolved', style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  for (final record in history.take(5))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        children: [
                          const Icon(Icons.check_circle_outline_rounded, size: 16),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(record.id, style: Theme.of(context).textTheme.bodySmall),
                          ),
                          Text(
                            _formatDateTime(record.updatedAt),
                            style: Theme.of(context).textTheme.labelSmall,
                          ),
                        ],
                      ),
                    ),
                ],
              ],
            );
          },
        ),
      );
}

class _IncidentRow extends StatelessWidget {
  const _IncidentRow({
    required this.incident,
    required this.lifecycle,
    required this.busy,
    required this.onAcknowledge,
    required this.onResolve,
    required this.onReopen,
  });

  final SirisIncident incident;
  final IncidentLifecycleRecord? lifecycle;
  final bool busy;
  final VoidCallback onAcknowledge;
  final VoidCallback onResolve;
  final VoidCallback onReopen;

  @override
  Widget build(BuildContext context) {
    final status = switch (incident.severity) {
      SirisIncidentSeverity.info => SirisStatus.info,
      SirisIncidentSeverity.warning => SirisStatus.warning,
      SirisIncidentSeverity.critical => SirisStatus.critical,
    };
    final lifecycleStatus = lifecycle?.status ?? IncidentLifecycleStatus.open;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(
              incident.isCritical
                  ? Icons.error_rounded
                  : Icons.warning_amber_rounded,
              size: 19,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(incident.title,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(
                  incident.summary,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                if (incident.affectedIntegrations.isNotEmpty) ...[
                  const SizedBox(height: 5),
                  Text(
                    'Affected: ${incident.affectedIntegrations.join(', ')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
                if (incident.dependencyImpacts.isNotEmpty) ...[
                  const SizedBox(height: 5),
                  Text(
                    'Declared downstream: ${incident.dependencyImpacts.map((item) => item.node.label).join(', ')}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ],
                const SizedBox(height: 5),
                Text(
                  '${incident.policyOutcomes.length} signal${incident.policyOutcomes.length == 1 ? '' : 's'} · since ${_formatDateTime(incident.startedAt)}',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
                const SizedBox(height: 3),
                Text(
                  incident.correlationReason,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
                if (lifecycleStatus == IncidentLifecycleStatus.resolved) ...[
                  const SizedBox(height: 3),
                  Text(
                    'Marked resolved but the underlying condition is still active.',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Theme.of(context).colorScheme.error,
                        ),
                  ),
                ],
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    if (lifecycleStatus == IncidentLifecycleStatus.open)
                      OutlinedButton(
                        onPressed: busy ? null : onAcknowledge,
                        child: const Text('Acknowledge'),
                      ),
                    if (lifecycleStatus != IncidentLifecycleStatus.resolved)
                      FilledButton(
                        onPressed: busy ? null : onResolve,
                        child: const Text('Resolve'),
                      ),
                    if (lifecycleStatus != IncidentLifecycleStatus.open)
                      TextButton(
                        onPressed: busy ? null : onReopen,
                        child: const Text('Reopen'),
                      ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              SirisStatusChip(
                  label: incident.severity.name.toUpperCase(), status: status),
              if (lifecycleStatus != IncidentLifecycleStatus.open) ...[
                const SizedBox(height: 6),
                SirisStatusChip(
                  label: lifecycleStatus == IncidentLifecycleStatus.resolved ? 'RESOLVED' : 'ACKNOWLEDGED',
                  status: lifecycleStatus == IncidentLifecycleStatus.resolved
                      ? SirisStatus.success
                      : SirisStatus.info,
                ),
              ],
            ],
          ),
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
      SirisConnectorState.disabled ||
      SirisConnectorState.disconnected =>
        SirisStatus.neutral,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(connector.label,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
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

class _RecommendationsPanel extends StatefulWidget {
  const _RecommendationsPanel();

  @override
  State<_RecommendationsPanel> createState() => _RecommendationsPanelState();
}

class _RecommendationsPanelState extends State<_RecommendationsPanel> {
  final _service = RecommendationService();
  final _actionService = ActionService();
  late Future<List<RecommendationRecord>> _future;
  final Set<String> _busy = {};

  @override
  void initState() {
    super.initState();
    _future = _service.list(status: RecommendationStatus.pending);
  }

  void _refresh() {
    setState(() {
      _future = _service.list(status: RecommendationStatus.pending);
    });
  }

  Future<void> _updateStatus(
      RecommendationRecord item, RecommendationStatus status) async {
    setState(() => _busy.add(item.id));
    try {
      await _service.updateStatus(item.id, status);
      _refresh();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to update recommendation.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy.remove(item.id));
    }
  }

  Future<void> _run(RecommendationRecord item) async {
    final capabilityId = item.capabilityId;
    if (capabilityId == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Run this action?'),
        content: Text(
          '${_capabilityLabel(capabilityId)} for ${item.title}. This runs immediately.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Run'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _busy.add(item.id));
    try {
      final result = await _actionService.execute(
        capabilityId,
        item.capabilityParams ?? const {},
      );
      await _service.updateStatus(item.id, RecommendationStatus.acted);
      _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(result)));
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _busy.remove(item.id));
    }
  }

  static String _capabilityLabel(String capabilityId) => switch (capabilityId) {
        'docker.start' => 'Start container',
        'docker.stop' => 'Stop container',
        'docker.restart' => 'Restart container',
        _ => capabilityId,
      };

  @override
  Widget build(BuildContext context) {
    return SirisPanel(
      title: 'Recommendations',
      subtitle: 'Deterministic suggestions from current alert evidence',
      icon: Icons.lightbulb_outline_rounded,
      child: FutureBuilder<List<RecommendationRecord>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 10),
              child: LinearProgressIndicator(),
            );
          }
          if (snapshot.hasError) {
            return _EmptyState(
              icon: Icons.error_outline_rounded,
              title: 'Unable to load recommendations',
              message: '${snapshot.error}',
            );
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const _EmptyState(
              icon: Icons.task_alt_rounded,
              title: 'No open recommendations',
              message: 'SirisOS has no evidence-based suggestions right now.',
            );
          }
          return Column(
            children: items
                .map(
                  (item) => _RecommendationRow(
                    item: item,
                    busy: _busy.contains(item.id),
                    onDismiss: () =>
                        _updateStatus(item, RecommendationStatus.dismissed),
                    onAct: () =>
                        _updateStatus(item, RecommendationStatus.acted),
                    onRun: item.capabilityId == null ? null : () => _run(item),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }
}

class _RecommendationRow extends StatelessWidget {
  const _RecommendationRow({
    required this.item,
    required this.busy,
    required this.onDismiss,
    required this.onAct,
    required this.onRun,
  });

  final RecommendationRecord item;
  final bool busy;
  final VoidCallback onDismiss;
  final VoidCallback onAct;
  final VoidCallback? onRun;

  @override
  Widget build(BuildContext context) {
    final status = item.severity == 'critical'
        ? SirisStatus.critical
        : SirisStatus.warning;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(
              item.severity == 'critical'
                  ? Icons.error_rounded
                  : Icons.warning_amber_rounded,
              size: 19,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.title,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(
                  item.displayRationale,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 5),
                Text(
                  item.suggestedAction,
                  style: Theme.of(context)
                      .textTheme
                      .labelSmall
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                if (busy)
                  const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  Row(
                    children: [
                      TextButton(
                          onPressed: onDismiss, child: const Text('Dismiss')),
                      const SizedBox(width: 6),
                      if (onRun != null)
                        FilledButton.icon(
                          onPressed: onRun,
                          icon: const Icon(Icons.bolt_rounded, size: 16),
                          label: const Text('Run'),
                        )
                      else
                        FilledButton.tonal(
                            onPressed: onAct, child: const Text('Mark acted')),
                    ],
                  ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          SirisStatusChip(label: item.severity.toUpperCase(), status: status),
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
    final failed = health.entries
        .where((entry) => entry.value.hasError)
        .toList(growable: false);
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
                    icon: policy.isCritical
                        ? Icons.priority_high_rounded
                        : Icons.warning_rounded,
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
  const _AttentionRow(
      {required this.icon, required this.title, required this.detail});

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
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
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
  const _EmptyState(
      {required this.icon, required this.title, required this.message});

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
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(
                    message,
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant),
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
