import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/models/jefit_import_result.dart';

void main() {
  test('parses a populated import result', () {
    final result = JefitImportResult.fromJson({
      'sessions_imported': 859,
      'sessions_skipped': 0,
      'sets_imported': 11182,
      'earliest_date': '2020-01-23',
      'latest_date': '2026-08-23',
      'errors': [],
    });

    expect(result.sessionsImported, 859);
    expect(result.setsImported, 11182);
    expect(result.earliestDate, DateTime(2020, 1, 23));
    expect(result.errors, isEmpty);
  });

  test('parses null dates and a populated errors list', () {
    final result = JefitImportResult.fromJson({
      'sessions_imported': 0,
      'sessions_skipped': 0,
      'sets_imported': 0,
      'earliest_date': null,
      'latest_date': null,
      'errors': ['No exercise log sessions found in this export.'],
    });

    expect(result.earliestDate, isNull);
    expect(result.latestDate, isNull);
    expect(result.errors, ['No exercise log sessions found in this export.']);
  });
}
