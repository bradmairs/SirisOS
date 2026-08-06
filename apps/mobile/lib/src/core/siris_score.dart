import '../models/dashboard_summary.dart';

enum SirisScoreDomain { health, running, gym, homelab, system }

class SirisScoreContribution {
  const SirisScoreContribution({
    required this.domain,
    required this.score,
    required this.weight,
    required this.explanation,
  });

  final SirisScoreDomain domain;
  final int score;
  final double weight;
  final String explanation;
}

class SirisScoreResult {
  const SirisScoreResult({
    required this.score,
    required this.contributions,
  });

  final int score;
  final List<SirisScoreContribution> contributions;

  List<String> get explanations => contributions
      .map((contribution) => contribution.explanation)
      .toList(growable: false);
}

class DeterministicSirisScore {
  const DeterministicSirisScore();

  SirisScoreResult calculate(DashboardSummary dashboard) {
    final contributions = <SirisScoreContribution>[
      _statusContribution(
        domain: SirisScoreDomain.homelab,
        status: dashboard.homelab.status,
        weight: 0.25,
        healthy: 'Homelab health supports the score.',
        warning: 'Homelab warnings reduce the score.',
      ),
      _statusContribution(
        domain: SirisScoreDomain.system,
        status: dashboard.system.status,
        weight: 0.20,
        healthy: 'Server health supports the score.',
        warning: 'Server health issues reduce the score.',
      ),
      _statusContribution(
        domain: SirisScoreDomain.running,
        status: dashboard.running.status,
        weight: 0.20,
        healthy: 'Running consistency supports the score.',
        warning: 'Running needs attention and lowers the score.',
      ),
      _statusContribution(
        domain: SirisScoreDomain.gym,
        status: dashboard.gym.status,
        weight: 0.20,
        healthy: 'Gym consistency supports the score.',
        warning: 'Gym activity needs attention and lowers the score.',
      ),
      _healthContribution(dashboard),
    ];

    final weighted = contributions.fold<double>(
      0,
      (total, contribution) =>
          total + (contribution.score * contribution.weight),
    );
    final totalWeight = contributions.fold<double>(
      0,
      (total, contribution) => total + contribution.weight,
    );
    final score = totalWeight == 0 ? 0 : (weighted / totalWeight).round();

    return SirisScoreResult(
      score: score.clamp(0, 100).toInt(),
      contributions: contributions,
    );
  }

  SirisScoreContribution _healthContribution(DashboardSummary dashboard) {
    final health = dashboard.health;
    if (health == null || !health.endpointConfigured) {
      return const SirisScoreContribution(
        domain: SirisScoreDomain.health,
        score: 50,
        weight: 0.15,
        explanation: 'Health data is not configured, so the domain is neutral.',
      );
    }
    if (!health.available) {
      return const SirisScoreContribution(
        domain: SirisScoreDomain.health,
        score: 35,
        weight: 0.15,
        explanation: 'Unavailable health data lowers confidence in the score.',
      );
    }

    final sleep = health.metrics.where((metric) {
      final name = metric.name.toLowerCase();
      return name == 'sleep' ||
          name == 'sleep_duration' ||
          name == 'sleep_analysis';
    }).firstOrNull;
    final sleepValue = sleep?.value;
    final hours = sleepValue is num
        ? sleepValue.toDouble()
        : double.tryParse(sleepValue?.toString() ?? '');

    if (hours == null) {
      return const SirisScoreContribution(
        domain: SirisScoreDomain.health,
        score: 70,
        weight: 0.15,
        explanation: 'Health data is available, but recovery metrics are limited.',
      );
    }
    if (hours < 6) {
      return SirisScoreContribution(
        domain: SirisScoreDomain.health,
        score: 40,
        weight: 0.15,
        explanation: 'Low sleep (${sleep!.displayValue}) reduces the score.',
      );
    }
    if (hours >= 7) {
      return SirisScoreContribution(
        domain: SirisScoreDomain.health,
        score: 90,
        weight: 0.15,
        explanation: 'Strong sleep (${sleep!.displayValue}) raises the score.',
      );
    }
    return SirisScoreContribution(
      domain: SirisScoreDomain.health,
      score: 70,
      weight: 0.15,
      explanation: 'Moderate sleep (${sleep!.displayValue}) is neutral-positive.',
    );
  }

  SirisScoreContribution _statusContribution({
    required SirisScoreDomain domain,
    required String status,
    required double weight,
    required String healthy,
    required String warning,
  }) {
    final normalized = status.toLowerCase();
    final critical = normalized == 'critical' || normalized == 'error';
    final problem = critical ||
        normalized == 'warning' ||
        normalized == 'unhealthy';
    return SirisScoreContribution(
      domain: domain,
      score: critical ? 20 : problem ? 50 : 90,
      weight: weight,
      explanation: problem ? warning : healthy,
    );
  }
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
