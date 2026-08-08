import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:siris_os/src/theme/app_theme.dart';

void main() {
  test('tonal action buttons use a visible foreground and container', () {
    final scheme = AppTheme.dark.colorScheme;

    expect(scheme.onSecondaryContainer, Colors.white);
    expect(scheme.secondaryContainer, isNot(equals(AppTheme.surface)));
    expect(scheme.secondaryContainer.computeLuminance(), greaterThan(0.015));
  });
}
