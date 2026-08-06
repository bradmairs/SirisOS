import '../models/dashboard_summary.dart';
import 'briefing_engine.dart';
import 'siris_score.dart';

class SirisAIContext {
  const SirisAIContext({
    required this.generatedAt,
    required this.sirisScore,
    required this.briefing,
    required this.facts,
  });

  final DateTime generatedAt;
  final SirisScoreResult sirisScore;
  final List<String> briefing;
  final Map<String, String> facts;

  String toPromptContext() {
    final buffer = StringBuffer()
      ..writeln('SirisOS context generated at ${generatedAt.toIso8601String()}')
      ..writeln('Siris Score: ${sirisScore.score}/100')
      ..writeln('What matters now:');
    for (final item in briefing) {
      buffer.writeln('- $item');
    }
    buffer.writeln('Current module facts:');
    for (final entry in facts.entries) {
      buffer.writeln('- ${entry.key}: ${entry.value}');
    }
    return buffer.toString().trim();
  }
}

class SirisAIContextService {
  SirisAIContextService({
    DeterministicBriefingEngine? briefingEngine,
    DeterministicSirisScore? scoreEngine,
  })  : _briefingEngine = briefingEngine ?? DeterministicBriefingEngine(),
        _scoreEngine = scoreEngine ?? const DeterministicSirisScore();

  final DeterministicBriefingEngine _briefingEngine;
  final DeterministicSirisScore _scoreEngine;

  SirisAIContext build(DashboardSummary dashboard) => SirisAIContext(
        generatedAt: DateTime.now(),
        sirisScore: _scoreEngine.calculate(dashboard),
        briefing: _briefingEngine.assemble(dashboard),
        facts: {
          'Homelab': '${dashboard.homelab.value} — ${dashboard.homelab.subtitle}',
          'Server': '${dashboard.system.value} — ${dashboard.system.subtitle}',
          'Running': '${dashboard.running.value} — ${dashboard.running.subtitle}',
          'Gym': '${dashboard.gym.value} — ${dashboard.gym.subtitle}',
          'Health': dashboard.health == null
              ? 'No snapshot available'
              : dashboard.health!.available
                  ? '${dashboard.health!.metrics.length} current metrics'
                  : dashboard.health!.error ?? 'Health service unavailable',
        },
      );
}
