import 'dart:math' as math;

import 'package:flutter/material.dart';

/// SirisOS brand mark.
///
/// The original red Siris S artwork remains the hero element, with the OS
/// designation now integrated directly beneath it and separated by the red
/// illuminated rule from the approved SirisOS branding direction.
class SirisLogo extends StatelessWidget {
  const SirisLogo({this.size = 56, this.showWordmark = true, super.key});

  static const _assetPath = 'assets/branding/siris_logo_red.webp';

  final double size;
  final bool showWordmark;

  @override
  Widget build(BuildContext context) {
    final width = showWordmark ? size * 2.05 : size;

    return Semantics(
      label: 'SirisOS',
      image: true,
      child: SizedBox(
        width: width,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _SMark(width: width),
            SizedBox(height: size * 0.035),
            _Separator(width: width * 0.70),
            SizedBox(height: size * 0.075),
            _OsMark(baseSize: size),
            if (showWordmark) ...[
              SizedBox(height: size * 0.13),
              _SirisOsWordmark(baseSize: size),
            ],
          ],
        ),
      ),
    );
  }
}

class _SMark extends StatelessWidget {
  const _SMark({required this.width});

  final double width;

  @override
  Widget build(BuildContext context) {
    // The source artwork is portrait-oriented; this viewport intentionally
    // keeps the upper S and clips the legacy lower treatment.
    return SizedBox(
      width: width,
      height: width * 0.72,
      child: ClipRect(
        child: Align(
          alignment: Alignment.topCenter,
          child: SizedBox(
            width: width,
            height: width * (667 / 468),
            child: Image.asset(
              SirisLogo._assetPath,
              alignment: Alignment.topCenter,
              fit: BoxFit.fill,
              filterQuality: FilterQuality.high,
              errorBuilder: (context, error, stackTrace) => _FallbackS(width: width),
            ),
          ),
        ),
      ),
    );
  }
}

class _Separator extends StatelessWidget {
  const _Separator({required this.width});

  final double width;

  @override
  Widget build(BuildContext context) => Container(
        width: width,
        height: 2.2,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(99),
          gradient: const LinearGradient(
            colors: [Colors.transparent, Color(0xFFFF2638), Color(0xFFFF2638), Colors.transparent],
            stops: [0, 0.18, 0.82, 1],
          ),
          boxShadow: const [
            BoxShadow(color: Color(0xCCFF182D), blurRadius: 8),
            BoxShadow(color: Color(0x88FF182D), blurRadius: 16),
          ],
        ),
      );
}

class _OsMark extends StatelessWidget {
  const _OsMark({required this.baseSize});

  final double baseSize;

  @override
  Widget build(BuildContext context) {
    final fontSize = math.max(14.0, baseSize * 0.44);
    return ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (bounds) => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFFFFFFFF), Color(0xFFF2F2F3), Color(0xFF8D8F94), Color(0xFFE7E7E9)],
        stops: [0, 0.30, 0.72, 1],
      ).createShader(bounds),
      child: Text(
        'OS',
        style: TextStyle(
          color: Colors.white,
          fontSize: fontSize,
          fontWeight: FontWeight.w800,
          letterSpacing: baseSize * 0.16,
          height: 0.92,
          shadows: const [Shadow(color: Color(0xFF000000), blurRadius: 8, offset: Offset(0, 3))],
        ),
      ),
    );
  }
}

class _SirisOsWordmark extends StatelessWidget {
  const _SirisOsWordmark({required this.baseSize});

  final double baseSize;

  @override
  Widget build(BuildContext context) => RichText(
        text: TextSpan(
          style: TextStyle(
            fontSize: math.max(13.0, baseSize * 0.27),
            fontWeight: FontWeight.w700,
            letterSpacing: baseSize * 0.09,
          ),
          children: const [
            TextSpan(text: 'SIRIS', style: TextStyle(color: Color(0xFFDADADD))),
            TextSpan(text: 'OS', style: TextStyle(color: Color(0xFFFF2638))),
          ],
        ),
      );
}

class _FallbackS extends StatelessWidget {
  const _FallbackS({required this.width});

  final double width;

  @override
  Widget build(BuildContext context) => Center(
        child: Text(
          'S',
          style: TextStyle(
            color: const Color(0xFFFF2638),
            fontSize: width * 0.62,
            fontWeight: FontWeight.w900,
            fontStyle: FontStyle.italic,
            height: 1,
            shadows: const [
              Shadow(color: Color(0xFFFF1027), blurRadius: 20),
              Shadow(color: Color(0xFF000000), blurRadius: 12, offset: Offset(0, 5)),
            ],
          ),
        ),
      );
}
