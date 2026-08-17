import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/core/muscle_readiness.dart';

void main() {
  group('level', () {
    test('no data when the group has never been trained', () {
      expect(
        MuscleReadiness.level(daysSinceTrained: null, fatigueFraction: 0),
        MuscleReadinessLevel.noData,
      );
    });

    test('ready once decayed load has fallen back near zero', () {
      expect(
        MuscleReadiness.level(daysSinceTrained: 4, fatigueFraction: 0.0),
        MuscleReadinessLevel.ready,
      );
    });

    test('recovering in the middle of the window', () {
      expect(
        MuscleReadiness.level(daysSinceTrained: 1, fatigueFraction: 0.4),
        MuscleReadinessLevel.recovering,
      );
    });

    test('fatigued right after a heavy, recent session', () {
      expect(
        MuscleReadiness.level(daysSinceTrained: 0, fatigueFraction: 1.0),
        MuscleReadinessLevel.fatigued,
      );
    });
  });

  group('label', () {
    test('maps each level to its display text', () {
      expect(MuscleReadiness.label(MuscleReadinessLevel.ready), 'Ready');
      expect(MuscleReadiness.label(MuscleReadinessLevel.recovering), 'Recovering');
      expect(MuscleReadiness.label(MuscleReadinessLevel.fatigued), 'Fatigued');
      expect(MuscleReadiness.label(MuscleReadinessLevel.noData), 'No data yet');
    });
  });

  group('daysUntilReady', () {
    final now = DateTime(2026, 8, 17, 9);

    test('null when there is no readyAt estimate', () {
      expect(
        MuscleReadiness.daysUntilReady(readyAt: null, fatigueFraction: 0.8, now: now),
        isNull,
      );
    });

    test('null once already effectively ready, even if readyAt is in the future', () {
      expect(
        MuscleReadiness.daysUntilReady(
          readyAt: now.add(const Duration(days: 2)),
          fatigueFraction: 0.02,
          now: now,
        ),
        isNull,
      );
    });

    test('counts whole days remaining until the estimate', () {
      expect(
        MuscleReadiness.daysUntilReady(
          readyAt: now.add(const Duration(days: 2)),
          fatigueFraction: 0.5,
          now: now,
        ),
        2,
      );
    });

    test('clamps to zero rather than going negative once the window has passed', () {
      expect(
        MuscleReadiness.daysUntilReady(
          readyAt: now.subtract(const Duration(days: 1)),
          fatigueFraction: 0.5,
          now: now,
        ),
        0,
      );
    });
  });
}
