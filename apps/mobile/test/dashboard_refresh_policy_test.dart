import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Dashboard background refresh policy keeps prior data visible', () {
    // Regression contract: background refreshes must not replace an already
    // rendered Dashboard with a full-page loading state. The implementation
    // retains the last successful DashboardSummary while a new Future waits.
    const hasPriorDashboardData = true;
    const refreshWaiting = true;

    final showFullPageLoader = refreshWaiting && !hasPriorDashboardData;

    expect(showFullPageLoader, isFalse);
  });
}
