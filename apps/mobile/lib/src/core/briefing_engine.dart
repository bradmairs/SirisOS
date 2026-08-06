import '../models/dashboard_summary.dart';

enum BriefingPriority { low, normal, high, critical }

enum BriefingTone { information, success, warning, critical }

class BriefingObservation {
  const BriefingObservation({
    required this.id,
    required this.moduleId,
    required this.message,
    required this.priority,
    required this.tone,
    this.expiresAt,
  });

  final String id;
  final String moduleId;
  final String message;
  final BriefingPriority priority;
  final BriefingTone tone;
  final DateTime? expiresAt;

  bool isActiveAt(DateTime now) => expiresAt == null || expiresAt!.isAfter(now);
}

abstract interface class BriefingContributor {
  String get moduleId;

  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  );
}

class DeterministicBriefingEngine {
  DeterministicBriefingEngine({List<BriefingContributor>? contributors})
      : contributors = contributors ??
            const [
              HomelabBriefingContributor(),
              RunningBriefingContributor(),
              GymBriefingContributor(),
              HealthBriefingContributor(),
            ];

  final List<BriefingContributor> contributors;

  List<BriefingObservation> observations(
    DashboardSummary dashboard, {
    DateTime? now,
  }) {
    final generatedAt = now ?? DateTime.now();
    final byId = <String, BriefingObservation>{};

    for (final contributor in contributors) {
      for (final observation in contributor.contribute(dashboard, generatedAt)) {
        if (observation.isActiveAt(generatedAt)) {
          byId[observation.id] = observation;
        }
      }
    }

    final ranked = byId.values.toList(growable: false)
      ..sort((a, b) {
        final priority = b.priority.index.compareTo(a.priority.index);
        if (priority != 0) return priority;
        return a.moduleId.compareTo(b.moduleId);
      });
    return ranked;
  }

  List<String> assemble(
    DashboardSummary dashboard, {
    DateTime? now,
    int limit = 4,
  }) {
    final generated = observations(dashboard, now: now)
        .take(limit)
        .map((observation) => observation.message)
        .toList(growable: false);

    if (generated.isNotEmpty) return generated;
    if (dashboard.briefingItems.isNotEmpty) {
      return dashboard.briefingItems.take(limit).toList(growable: false);
    }
    return const ['SirisOS is operating normally.'];
  }
}

class HomelabBriefingContributor implements BriefingContributor {
  const HomelabBriefingContributor();

  @override
  String get moduleId => 'homelab';

  @override
  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  ) sync* {
    final homelab = dashboard.homelab;
    final system = dashboard.system;

    if (_isProblem(homelab.status)) {
      yield BriefingObservation(
        id: 'homelab.attention',
        moduleId: moduleId,
        message: '${homelab.title} needs attention: ${homelab.subtitle}',
        priority: _isCritical(homelab.status)
            ? BriefingPriority.critical
            : BriefingPriority.high,
        tone: _isCritical(homelab.status)
            ? BriefingTone.critical
            : BriefingTone.warning,
      );
    } else {
      yield BriefingObservation(
        id: 'homelab.healthy',
        moduleId: moduleId,
        message: 'Homelab services are reporting normally.',
        priority: BriefingPriority.low,
        tone: BriefingTone.success,
      );
    }

    if (_isProblem(system.status)) {
      yield BriefingObservation(
        id: 'homelab.system-attention',
        moduleId: moduleId,
        message: '${system.title} needs attention: ${system.subtitle}',
        priority: BriefingPriority.high,
        tone: BriefingTone.warning,
      );
    }
  }
}

class RunningBriefingContributor implements BriefingContributor {
  const RunningBriefingContributor();

  @override
  String get moduleId => 'running';

  @override
  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  ) sync* {
    final running = dashboard.running;
    if (_isProblem(running.status)) {
      yield BriefingObservation(
        id: 'running.attention',
        moduleId: moduleId,
        message: '${running.title}: ${running.subtitle}',
        priority: BriefingPriority.high,
        tone: BriefingTone.warning,
      );
    } else if (running.value != '—') {
      yield BriefingObservation(
        id: 'running.summary',
        moduleId: moduleId,
        message: '${running.title}: ${running.value}. ${running.subtitle}',
        priority: BriefingPriority.normal,
        tone: BriefingTone.information,
      );
    }
  }
}

class GymBriefingContributor implements BriefingContributor {
  const GymBriefingContributor();

  @override
  String get moduleId => 'gym';

  @override
  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  ) sync* {
    final gym = dashboard.gym;
    if (_isProblem(gym.status)) {
      yield BriefingObservation(
        id: 'gym.attention',
        moduleId: moduleId,
        message: '${gym.title}: ${gym.subtitle}',
        priority: BriefingPriority.high,
        tone: BriefingTone.warning,
      );
    } else if (gym.value != '—') {
      yield BriefingObservation(
        id: 'gym.summary',
        moduleId: moduleId,
        message: '${gym.title}: ${gym.value}. ${gym.subtitle}',
        priority: BriefingPriority.normal,
        tone: BriefingTone.information,
      );
    }
  }
}

/// Health is registered as a first-class contributor now, while the dashboard
/// summary does not yet expose a dedicated health card. It deliberately emits
/// no fabricated observation until health data is added to the shared input.
class HealthBriefingContributor implements BriefingContributor {
  const HealthBriefingContributor();

  @override
  String get moduleId => 'health';

  @override
  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  ) => const [];
}

bool _isProblem(String status) {
  final normalized = status.toLowerCase();
  return normalized == 'warning' ||
      normalized == 'critical' ||
      normalized == 'error' ||
      normalized == 'unhealthy';
}

bool _isCritical(String status) {
  final normalized = status.toLowerCase();
  return normalized == 'critical' || normalized == 'error';
}
