import 'package:flutter/material.dart';

enum MissionControlWidgetSize { compact, standard, wide }

class MissionControlWidgetDefinition {
  const MissionControlWidgetDefinition({
    required this.id,
    required this.moduleId,
    required this.label,
    required this.description,
    required this.icon,
    required this.defaultSize,
  });

  final String id;
  final String moduleId;
  final String label;
  final String description;
  final IconData icon;
  final MissionControlWidgetSize defaultSize;
}
