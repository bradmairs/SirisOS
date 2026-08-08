import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/config/display_config.dart';

void main() {
  test('host alias hides the raw canonical hostname by default', () {
    expect(DisplayConfig.hostLabel('c4cf79554e11'), 'Linux Server');
  });

  test('UPS alias replaces unavailable NUT descriptions by default', () {
    expect(
      DisplayConfig.upsLabel(
        description: 'Description Unavailable',
        canonicalName: 'ups',
      ),
      'Server UPS',
    );
  });
}
