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

    // Front and back share every shape except the torso overlay (chest vs.
    // back) -- traced by hand as smooth bezier paths rather than primitive
    // rects/ellipses so the figure actually reads as a body: a tapered
    // waist, rounded deltoid caps, and arms/legs with real negative space
    // between them and the torso instead of touching blocks.
    final torsoOverlay = front
        ? 'M80,90 C96,98 144,98 160,90 L154,138 C140,150 100,150 86,138 Z'
        : 'M80,90 C96,98 144,98 160,90 L152,172 C138,182 102,182 88,172 Z';

    final svg = '''
<svg viewBox="0 0 240 560" xmlns="http://www.w3.org/2000/svg">
  <path d="M72,88 C90,96 150,96 168,88 L160,140 C154,175 150,195 145,215 C158,225 156,245 152,255 L120,270 L88,255 C84,245 82,225 95,215 C90,195 86,175 80,140 Z" fill="$core" stroke="$outline" stroke-width="2"/>
  <path d="M152,258 C158,270 156,290 152,320 L144,420 C142,460 140,495 138,515 L126,515 C124,480 122,440 120,400 L120,300 C120,285 122,270 122,262 Z" fill="$legs" stroke="$outline" stroke-width="2"/>
  <path d="M88,258 C82,270 84,290 88,320 L96,420 C98,460 100,495 102,515 L114,515 C116,480 118,440 120,400 L120,300 C120,285 118,270 118,262 Z" fill="$legs" stroke="$outline" stroke-width="2"/>
  <circle cx="172" cy="96" r="25" fill="$shoulders" stroke="$outline" stroke-width="2"/>
  <circle cx="68" cy="96" r="25" fill="$shoulders" stroke="$outline" stroke-width="2"/>
  <path d="M172,92 C186,98 198,120 200,148 C202,178 196,206 190,228 L188,290 L168,286 L172,224 C168,196 166,164 168,136 C169,120 170,104 172,92 Z" fill="$arms" stroke="$outline" stroke-width="2"/>
  <path d="M68,92 C54,98 42,120 40,148 C38,178 44,206 50,228 L52,290 L72,286 L68,224 C72,196 74,164 72,136 C71,120 70,104 68,92 Z" fill="$arms" stroke="$outline" stroke-width="2"/>
  <path d="$torsoOverlay" fill="$torso" stroke="$outline" stroke-width="2"/>
  <path d="M110,70 C110,84 108,88 104,92 L106,96 C114,100 126,100 134,96 L136,92 C132,88 130,84 130,70 Z" fill="$neutral" stroke="$outline" stroke-width="2"/>
  <ellipse cx="120" cy="42" rx="25" ry="29" fill="$neutral" stroke="$outline" stroke-width="2"/>
</svg>
''';

    return SvgPicture.string(svg, semanticsLabel: front ? 'Front body view' : 'Back body view');
  }
}
