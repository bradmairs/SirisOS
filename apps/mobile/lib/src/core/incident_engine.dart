import 'dependency_graph.dart';
import 'notification_policy.dart';
import 'siris_connector.dart';

enum SirisIncidentSeverity { info, warning, critical }

class SirisIncident {
  const SirisIncident({
    required this.id,
    required this.title,
    required this.summary,
    required this.severity,
    required this.startedAt,
    required this.policyOutcomes,
    required this.affectedIntegrations,
    required this.correlationReason,
    this.dependencyImpacts = const [],
  });

  final String id;
  final String title;
  final String summary;
  final SirisIncidentSeverity severity;
  final DateTime startedAt;
  final List<NotificationPolicyOutcome> policyOutcomes;
  final List<String> affectedIntegrations;
  final String correlationReason;
  final List<DependencyImpact> dependencyImpacts;

  bool get isCritical => severity == SirisIncidentSeverity.critical;
}

class IncidentEngine {
  IncidentEngine._();

  static final IncidentEngine instance = IncidentEngine._();

  List<SirisIncident> correlate({
    required List<NotificationPolicyOutcome> outcomes,
    required Map<String, SirisConnectorHealth> integrationHealth,
  }) {
    if (outcomes.isEmpty &&
        !integrationHealth.values.any((item) => item.hasError)) {
      return const <SirisIncident>[];
    }

    final remaining = [...outcomes];
    final incidents = <SirisIncident>[];

    final power = remaining
        .where((item) => item.id == 'ups.on_battery' || item.id == 'ups.low_battery')
        .toList(growable: false);
    if (power.isNotEmpty) {
      final related = remaining.where((item) {
        if (power.contains(item)) return true;
        return _powerRelatedPolicyIds.contains(item.id);
      }).toList(growable: false);
      remaining.removeWhere(related.contains);

      final affected = <String>{'UPS'};
      for (final entry in integrationHealth.entries) {
        if (entry.value.hasError && _powerRelatedIntegrations.contains(entry.key)) {
          affected.add(_integrationLabel(entry.key));
        }
      }
      for (final item in related) {
        final label = _policyIntegrationLabel(item.id);
        if (label != null) affected.add(label);
      }
      final lowBattery = power.any((item) => item.id == 'ups.low_battery');
      incidents.add(
        SirisIncident(
          id: 'incident.power',
          title: lowBattery ? 'Power outage — battery critical' : 'Power outage',
          summary: affected.length > 1
              ? 'Utility power is unavailable. ${affected.length - 1} dependent service${affected.length == 2 ? '' : 's'} also need attention.'
              : 'Utility power is unavailable and the UPS is supplying battery power.',
          severity: lowBattery || related.any((item) => item.isCritical)
              ? SirisIncidentSeverity.critical
              : SirisIncidentSeverity.warning,
          startedAt: _earliest(related),
          policyOutcomes: related,
          affectedIntegrations: affected.toList()..sort(),
          correlationReason:
              'UPS power-state policy is the anchor; concurrent infrastructure failures are attached as possible impacts.',
          dependencyImpacts: _declaredImpacts(related),
        ),
      );
    }

    for (final category in _categories) {
      final matched = remaining
          .where((item) => category.matches(item.id))
          .toList(growable: false);
      if (matched.isEmpty) continue;
      remaining.removeWhere(matched.contains);
      incidents.add(
        SirisIncident(
          id: 'incident.${category.id}',
          title: category.title,
          summary: matched.length == 1
              ? matched.first.rule.message
              : '${matched.length} related ${category.title.toLowerCase()} conditions are active.',
          severity: _highestSeverity(matched),
          startedAt: _earliest(matched),
          policyOutcomes: matched,
          affectedIntegrations: matched
              .map((item) => _policyIntegrationLabel(item.id))
              .whereType<String>()
              .toSet()
              .toList()
            ..sort(),
          correlationReason: category.reason,
          dependencyImpacts: _declaredImpacts(matched),
        ),
      );
    }

    for (final outcome in remaining) {
      final integrationLabel = _policyIntegrationLabel(outcome.id);
      incidents.add(
        SirisIncident(
          id: 'incident.policy.${outcome.id}',
          title: outcome.rule.title,
          summary: outcome.rule.message,
          severity: _fromPolicy(outcome.severity),
          startedAt: outcome.activatedAt,
          policyOutcomes: [outcome],
          affectedIntegrations: integrationLabel == null ? const [] : [integrationLabel],
          correlationReason: 'Standalone policy outcome; no stronger correlation rule matched.',
          dependencyImpacts: _declaredImpacts([outcome]),
        ),
      );
    }

    incidents.sort((a, b) {
      final severity = _severityRank(b.severity).compareTo(_severityRank(a.severity));
      if (severity != 0) return severity;
      return a.startedAt.compareTo(b.startedAt);
    });
    return incidents;
  }

  static List<DependencyImpact> _declaredImpacts(
    List<NotificationPolicyOutcome> outcomes,
  ) {
    final ids = outcomes
        .map((item) => _policyDependencyNodeId(item.id))
        .whereType<String>()
        .toSet();
    return DependencyGraph.instance.downstreamForMany(ids);
  }

  static final Set<String> _powerRelatedPolicyIds = {
    'docker.unhealthy',
    'docker.stopped',
    'synology.unavailable',
    'home_assistant.unavailable',
    'unifi.unavailable',
    'prometheus.unavailable',
    'grafana.unavailable',
  };

  static final Set<String> _powerRelatedIntegrations = {
    'docker',
    'synology',
    'home_assistant',
    'unifi',
    'prometheus',
    'grafana',
  };

  static const List<_IncidentCategory> _categories = [
    _IncidentCategory(
      id: 'backup',
      title: 'Backup protection issue',
      prefixes: ['synology.hyper_backup.', 'synology.backup', 'synology_backup', 'backup.'],
      reason: 'Backup-related policy outcomes are grouped into one data-protection incident.',
    ),
    _IncidentCategory(
      id: 'storage',
      title: 'Storage issue',
      prefixes: ['storage.', 'synology.storage', 'synology.unhealthy'],
      reason: 'Storage-capacity and NAS-health policy outcomes are grouped by subsystem.',
    ),
    _IncidentCategory(
      id: 'network',
      title: 'Network issue',
      prefixes: ['unifi.'],
      reason: 'UniFi network policy outcomes are grouped into one network incident.',
    ),
    _IncidentCategory(
      id: 'compute',
      title: 'Compute issue',
      prefixes: ['docker.'],
      reason: 'Docker runtime policy outcomes are grouped into one compute incident.',
    ),
    _IncidentCategory(
      id: 'observability',
      title: 'Monitoring issue',
      prefixes: ['prometheus.', 'grafana.'],
      reason: 'Observability-system policy outcomes are grouped together.',
    ),
    _IncidentCategory(
      id: 'automation',
      title: 'Home automation issue',
      prefixes: ['home_assistant.'],
      reason: 'Home Assistant policy outcomes are grouped into one automation incident.',
    ),
  ];

  static DateTime _earliest(List<NotificationPolicyOutcome> outcomes) {
    if (outcomes.isEmpty) return DateTime.now();
    return outcomes
        .map((item) => item.activatedAt)
        .reduce((a, b) => a.isBefore(b) ? a : b);
  }

  static SirisIncidentSeverity _highestSeverity(
    List<NotificationPolicyOutcome> outcomes,
  ) {
    if (outcomes.any((item) => item.severity == NotificationPolicySeverity.critical)) {
      return SirisIncidentSeverity.critical;
    }
    if (outcomes.any((item) => item.severity == NotificationPolicySeverity.warning)) {
      return SirisIncidentSeverity.warning;
    }
    return SirisIncidentSeverity.info;
  }

  static SirisIncidentSeverity _fromPolicy(NotificationPolicySeverity severity) => switch (severity) {
        NotificationPolicySeverity.info => SirisIncidentSeverity.info,
        NotificationPolicySeverity.warning => SirisIncidentSeverity.warning,
        NotificationPolicySeverity.critical => SirisIncidentSeverity.critical,
      };

  static int _severityRank(SirisIncidentSeverity severity) => switch (severity) {
        SirisIncidentSeverity.info => 1,
        SirisIncidentSeverity.warning => 2,
        SirisIncidentSeverity.critical => 3,
      };

  static String _integrationLabel(String id) => switch (id) {
        'home_assistant' => 'Home Assistant',
        'unifi' => 'UniFi',
        'prometheus' => 'Prometheus',
        'grafana' => 'Grafana',
        'synology' => 'Synology',
        'docker' => 'Docker',
        _ => id,
      };

  static String? _policyIntegrationLabel(String policyId) {
    if (policyId.startsWith('docker.')) return 'Docker';
    if (policyId.startsWith('synology')) return 'Synology';
    if (policyId.startsWith('home_assistant.')) return 'Home Assistant';
    if (policyId.startsWith('unifi.')) return 'UniFi';
    if (policyId.startsWith('prometheus.')) return 'Prometheus';
    if (policyId.startsWith('grafana.')) return 'Grafana';
    if (policyId.startsWith('ups.')) return 'UPS';
    if (policyId.startsWith('storage.')) return 'Storage';
    return null;
  }

  static String? _policyDependencyNodeId(String policyId) {
    if (policyId.startsWith('docker.')) return 'docker';
    if (policyId.startsWith('synology.hyper_backup.')) return 'hyper_backup';
    if (policyId.startsWith('synology.')) return 'synology';
    if (policyId.startsWith('home_assistant.')) return 'home_assistant';
    if (policyId.startsWith('unifi.')) return 'unifi';
    if (policyId.startsWith('prometheus.')) return 'prometheus';
    if (policyId.startsWith('grafana.')) return 'grafana';
    if (policyId.startsWith('ups.')) return 'ups';
    return null;
  }
}

class _IncidentCategory {
  const _IncidentCategory({
    required this.id,
    required this.title,
    required this.prefixes,
    required this.reason,
  });

  final String id;
  final String title;
  final List<String> prefixes;
  final String reason;

  bool matches(String policyId) => prefixes.any(policyId.startsWith);
}
