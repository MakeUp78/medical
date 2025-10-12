#!/usr/bin/env python3
"""Test sistema query intelligenti"""

from voice.intelligent_query_handler import IntelligentQueryHandler

def test_queries():
    """Test del sistema di query intelligenti"""
    print('🧠 TEST SISTEMA QUERY INTELLIGENTI')
    print('=' * 50)

    try:
        # Test 1: Inizializzazione sistema
        handler = IntelligentQueryHandler()
        patterns = handler.patterns
        print(f'✅ Sistema inizializzato: {len(patterns)} pattern disponibili')
        
        # Test 2: Simulazione dati misurazione (come nell'app reale)
        test_data = {
            'distances': {
                'distanza_sa_da': 0.03,
                'distanza_sc_dc': 3.27,
                'distanza_sb_db': 4.92
            },
            'symmetry': {
                'differenza_altezza_sa_da': 0.15,
                'differenza_altezza_sc_dc': 1.67,
                'differenza_altezza_sb_db': 3.91
            },
            'areas': {
                'area_sopracciglio_sx': 897.5,
                'area_sopracciglio_dx': 945.0,
                'differenza_aree_sopracciglia': 47.5
            }
        }
        
        handler.analyzer.update_data(test_data)
        print(f'✅ Dati test caricati: {len(test_data)} categorie')
        
        # Test 3: Query di esempio
        test_queries = [
            'il punto SC è più alto del DC?',
            'quale sopracciglia è più grande?', 
            'quanto è la differenza tra le aree?',
            'i punti sono simmetrici?',
            'dimmi le distanze',
            'confronta i sopracciglia'
        ]
        
        print(f'\n📋 TEST QUERY:')
        for i, query in enumerate(test_queries, 1):
            result = handler.process_query(query)
            status = '✅ RISPOSTA' if result else '❌ NESSUNA RISPOSTA'
            print(f'{i}. "{query}"')
            print(f'   → {status}: {result or "Non trovata"}')
            print()
            
        # Test 4: Verifica pattern disponibili
        print('\n📝 PATTERN DISPONIBILI:')
        for pattern_id, pattern in patterns.items():
            print(f'- {pattern_id}: {pattern.keywords[:2]}...')
            
    except Exception as e:
        print(f'❌ Errore test: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_queries()