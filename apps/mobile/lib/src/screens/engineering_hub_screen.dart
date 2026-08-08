import 'package:flutter/material.dart';

import '../widgets/contextual_knowledge_panel.dart';
import 'engineering_screen.dart';
import 'engineering_standards_screen.dart';
import 'sirishydro_screen.dart';

class EngineeringHubScreen extends StatelessWidget {
  const EngineeringHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const DefaultTabController(
      length: 3,
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: ContextualKnowledgePanel(
              contextId: 'engineering',
              title: 'Engineering Knowledge',
              maxNotes: 2,
            ),
          ),
          Material(
            child: TabBar(
              tabs: [
                Tab(icon: Icon(Icons.calculate_rounded), text: 'Calculators'),
                Tab(icon: Icon(Icons.menu_book_rounded), text: 'Standards'),
                Tab(icon: Icon(Icons.water_drop_rounded), text: 'SirisHydro'),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                EngineeringScreen(),
                EngineeringStandardsScreen(),
                SirisHydroScreen(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
