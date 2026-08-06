import 'package:flutter_test/flutter_test.dart';
import 'package:sirisos/src/core/briefing_engine.dart';
import 'package:sirisos/src/models/dashboard_summary.dart';

void main() {
  const normal = DashboardCardData(
    title: 'Normal',
    value: 'OK',
    subtitle: 'All good',
    status: 'healthy',
  );

  test('critical observations rank before normal summaries', () {
    final dashboard = DashboardSummary(
      greetingName: 'Brad',
      homelab: const DashboardCardData(
        title: 'Homelab',
        value: '1 issue',
        subtitle: 'Container unhealthy',
        status: 'critical',
      ),
      running: const DashboardCardData(
        title: 'Running',
        value: '12 km',
        subtitle: 'This week',
        status: 'healthy',
      ),
      gym: normal,
      system: normal,
      briefingItems: const [],
      generatedAt: DateTime(2026, 8, 7),
    );

    final observations = DeterministicBriefingEngine().observations(dashboard);

    expect(observations.first.id, 'homelab.attention');
    expect(observations.first.priority, BriefingPriority.critical);
  });

  test('duplicate observation IDs are collapsed', () {
    final dashboard = DashboardSummary(
      greetingName: 'Brad',
      homelab: normal,
      running: normal,
      gym: normal,
      system: normal,
      briefingItems: const [],
      generatedAt: DateTime(2026, 8, 7),
    );

    final engine = DeterministicBriefingEngine(
      contributors: const [_DuplicateContributor(), _DuplicateContributor()],
    );

    expect(engine.observations(dashboard), hasLength(1));
  });
}

class _DuplicateContributor implements BriefingContributor {
  const _DuplicateContributor();

  @override
  String get moduleId => 'test';

  @override
  Iterable<BriefingObservation> contribute(
    DashboardSummary dashboard,
    DateTime now,
  ) => const [
        BriefingObservation(
          id: 'test.same',
          moduleId: 'test',
          message: 'Same observation',
          priority: BriefingPriority.normal,
          tone: BriefingTone.information,
        ),
      ];
}
