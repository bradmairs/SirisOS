import '../models/dashboard_summary.dart';
import '../models/health_snapshot.dart';

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

class HealthBriefingContributor implements BriefingContributor {
  const HealthBriefingContributor();

  @override
  String get moduleId => 'health';

  @override
  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  ) sync* {
    final health = dashboard.health;
    if (health == null) return;

    if (!health.endpointConfigured) {
      yield BriefingObservation(
        id: 'health.not-configured',
        moduleId: moduleId,
        message: 'Health data is not configured yet.',
        priority: BriefingPriority.low,
        tone: BriefingTone.information,
      );
      return;
    }

    if (!health.available) {
      yield BriefingObservation(
        id: 'health.unavailable',
        moduleId: moduleId,
        message: health.error?.isNotEmpty == true
            ? 'Health data is unavailable: ${health.error}'
            : 'Health data is currently unavailable.',
        priority: BriefingPriority.high,
        tone: BriefingTone.warning,
      );
      return;
    }

    final sleep = _metric(health, const ['sleep', 'sleep_duration', 'sleep_analysis']);
    final steps = _metric(health, const ['steps', 'step_count']);
    final restingHeartRate = _metric(health, const ['resting_heart_rate']);

    final sleepHours = _number(sleep);
    if (sleepHours != null) {
      if (sleepHours < 6) {
        yield BriefingObservation(
          id: 'health.sleep-low',
          moduleId: moduleId,
          message: 'Sleep was ${sleep!.displayValue}; recovery may need extra attention.',
          priority: BriefingPriority.high,
          tone: BriefingTone.warning,
        );
      } else if (sleepHours >= 7) {
        yield BriefingObservation(
          id: 'health.sleep-good',
          moduleId: moduleId,
          message: 'Sleep was ${sleep!.displayValue}, supporting a solid recovery day.',
          priority: BriefingPriority.normal,
          tone: BriefingTone.success,
        );
      }
    }

    if (steps != null) {
      yield BriefingObservation(
        id: 'health.steps',
        moduleId: moduleId,
        message: 'Latest activity: ${steps.displayValue} steps.',
        priority: BriefingPriority.low,
        tone: BriefingTone.information,
      );
    }

    if (restingHeartRate != null) {
      yield BriefingObservation(
        id: 'health.resting-heart-rate',
        moduleId: moduleId,
        message: 'Resting heart rate is ${restingHeartRate.displayValue}.',
        priority: BriefingPriority.low,
        tone: BriefingTone.information,
      );
    }
  }
}

HealthMetric? _metric(HealthSnapshot snapshot, List<String> names) {
  for (final metric in snapshot.metrics) {
    if (names.contains(metric.name.toLowerCase())) return metric;
  }
  return null;
}

double? _number(HealthMetric? metric) {
  final value = metric?.value;
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '');
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
