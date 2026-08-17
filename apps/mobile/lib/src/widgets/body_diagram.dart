import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../theme/app_theme.dart';

/// A simplified front/back body silhouette, split into the same six
/// muscle-group regions [GymService]/`MUSCLE_GROUPS` uses. Each region's
/// fill color is computed by the caller (see [MuscleMapCard]) and baked
/// into the SVG markup directly, rather than trying to recolor named paths
/// at render time -- flutter_svg has no first-class per-path theming API,
/// and generating the string ourselves keeps this self-contained (no
/// external asset to source or license).
class BodyDiagram extends StatelessWidget {
  const BodyDiagram({
    required this.front,
    required this.colors,
    super.key,
  });

  final bool front;
  final Map<String, Color> colors;

  static const _neutral = AppTheme.surfaceRaised;
  static const _outline = AppTheme.border;

  String _hex(Color color) {
    int byte(double v) => (v * 255).round().clamp(0, 255);
    final r = byte(color.r).toRadixString(16).padLeft(2, '0');
    final g = byte(color.g).toRadixString(16).padLeft(2, '0');
    final b = byte(color.b).toRadixString(16).padLeft(2, '0');
    return '#$r$g$b';
  }

  String _fill(String group) => _hex(colors[group] ?? _neutral);

  @override
  Widget build(BuildContext context) {
    final shoulders = _fill('shoulders');
    final torso = front ? _fill('chest') : _fill('back');
    final core = _fill('core');
    final arms = _fill('arms');
    final legs = _fill('legs');
    final outline = _hex(_outline);
    final neutral = _hex(_neutral);

    final torsoHeight = front ? 66 : 92;
    final coreY = front ? 150 : 176;
    final coreHeight = front ? 78 : 54;

    final svg = '''
<svg viewBox="0 0 220 460" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="110" cy="36" rx="24" ry="28" fill="$neutral" stroke="$outline" stroke-width="2"/>
  <rect x="98" y="58" width="24" height="18" rx="6" fill="$neutral" stroke="$outline" stroke-width="2"/>
  <rect x="26" y="94" width="32" height="176" rx="16" fill="$arms" stroke="$outline" stroke-width="2"/>
  <rect x="162" y="94" width="32" height="176" rx="16" fill="$arms" stroke="$outline" stroke-width="2"/>
  <rect x="72" y="222" width="36" height="210" rx="18" fill="$legs" stroke="$outline" stroke-width="2"/>
  <rect x="112" y="222" width="36" height="210" rx="18" fill="$legs" stroke="$outline" stroke-width="2"/>
  <ellipse cx="58" cy="98" rx="28" ry="24" fill="$shoulders" stroke="$outline" stroke-width="2"/>
  <ellipse cx="162" cy="98" rx="28" ry="24" fill="$shoulders" stroke="$outline" stroke-width="2"/>
  <rect x="66" y="88" width="88" height="$torsoHeight" rx="22" fill="$torso" stroke="$outline" stroke-width="2"/>
  <rect x="74" y="$coreY" width="72" height="$coreHeight" rx="18" fill="$core" stroke="$outline" stroke-width="2"/>
</svg>
''';

    return SvgPicture.string(svg, semanticsLabel: front ? 'Front body view' : 'Back body view');
  }
}
