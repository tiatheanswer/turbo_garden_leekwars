import requests
import json
import time
import logging
from datetime import datetime

class LeekWarsBot:
    def __init__(self, username, password):
        self.base_url = "https://leekwars.com/api/"
        self.session = requests.Session()
        self.username = username
        self.password = password
        
        # Variables pour la session
        self.php_session_id = None
        self.farmer_token = None
        self.lang = None
        self.cookies = {}
        self.farmer_info = {}
        self.farmer_leeks = None
        self.leek_opps = None

        # Configuration du logging (sans emojis pour Windows)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('leekwars_bot.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Headers standards selon le forum
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest'
        })
    
    def login(self):
        """Connexion selon la méthode confirmée du forum LeekWars"""
        try:
            self.logger.info("Connexion à LeekWars (méthode forum)...")
            
            # IMPORTANT: keep_connected doit être boolean selon l'erreur API
            login_data = {
                'login': self.username,
                'password': self.password,
                'keep_connected': True  # boolean, pas string !
            }
            
            response = self.session.post(
                f"{self.base_url}farmer/login-token",
                data=login_data
            )
            
            self.logger.info(f"Login Status: {response.status_code}")
            self.logger.info(f"Response: {response.text[:200]}...")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # Vérifier le succès
                    # if not result.get('success', False):
                    #     self.logger.error(f"Connexion échouée: {result}")
                    #     return False
                    
                    # Extraire les informations du fermier si disponibles
                    if 'farmer' in result:
                        self.farmer_info = result['farmer']
                        self.logger.info(f"Fermier connecté: {self.farmer_info.get('name', 'Inconnu')}")
                    
                    # CRUCIAL: Récupérer les cookies depuis les headers Set-Cookie
                    self.logger.info("Analyse des cookies de session...")
                    
                    cookies_found = []
                    for cookie in self.session.cookies:
                        cookies_found.append(f"{cookie.name}={cookie.value}")
                        
                        if cookie.name == 'PHPSESSID':
                            self.php_session_id = cookie.value
                            self.logger.info(f"PHPSESSID trouvé: {cookie.value[:20]}...")
                            
                        elif cookie.name.lower() == 'token' or 'token' in cookie.name.lower():
                            self.farmer_token = cookie.value
                            self.logger.info(f"Token trouvé: {cookie.name} = {cookie.value[:20]}...")
                    
                    self.logger.info(f"Cookies récupérés: {len(cookies_found)}")
                    for cookie_info in cookies_found:
                        self.logger.info(f"  - {cookie_info[:50]}...")
                    
                    # Vérifier qu'on a au moins PHPSESSID
                    if self.php_session_id:
                        self.logger.info("Session établie avec PHPSESSID")
                        self.cookies = self.session.cookies
                        return True
                    else:
                        self.logger.error("Aucun PHPSESSID trouvé dans les cookies")
                        return False
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Réponse non-JSON: {e}")
                    return False
                    
            else:
                self.logger.error(f"Erreur HTTP: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la connexion: {e}")
            return False
    
    def make_api_call(self, endpoint, params=None, method='POST'):
        """Effectue un appel API avec les cookies de session"""
        if params is None:
            params = {}
        
        # Debug pour voir les paramètres
        self.logger.debug(f"Appel API {endpoint} avec params: {params}")
        
        try:
            if method.upper() == 'POST':
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    data=params,  # Utiliser data au lieu de rien
                    cookies=self.cookies
                )
            else:  # GET
                response = self.session.get(
                    f"{self.base_url}{endpoint}",
                    params=params,  # Pour GET, utiliser params dans l'URL
                    cookies=self.cookies
                )
            
            self.logger.debug(f"{endpoint} - Status: {response.status_code}")
            self.logger.debug(f"URL finale: {response.url}")
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    self.logger.error(f"Réponse non-JSON pour {endpoint}: {response.text[:100]}")
                    return None
                    
            elif response.status_code == 401:
                self.logger.warning(f"Non autorisé pour {endpoint}, reconnexion...")
                if self.login():
                    # Retry une fois
                    time.sleep(2)  # Réduire le délai
                    return self.make_api_call(endpoint, params, method)
                return None
                
            elif response.status_code == 429:
                self.logger.warning("Rate limiting, attente...")
                time.sleep(15)
                return None
                
            else:
                self.logger.error(f"Erreur {endpoint}: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            self.logger.error(f"Erreur appel API {endpoint}: {e}")
            return None
    
    def test_api_access(self):
        """Teste l'accès à l'API après connexion"""
        self.logger.info("Test de l'accès API...")
        
        # Test 1: farmer/get
        farmer = self.make_api_call("farmer/get-from-token", method='GET')
        if farmer:
            if 'farmer' in farmer:
                farmer = farmer['farmer']
                self.logger.info(f"farmer/get OK - {farmer.get('name')} (ID: {farmer.get('id')})")
                return True
            else:
                self.logger.warning(f"farmer/get réponse inattendue: {farmer}")
        else:
            self.logger.error("farmer/get échoué")
            
        return False
    
    def get_farmer_info(self):
        """Récupère les informations du fermier"""
        result = self.make_api_call("farmer/get-from-token", method='GET')
        if result and 'farmer' in result:
            return result['farmer']
        return result
    
    def get_garden_farmer_opponents(self):
        """Récupère la liste des fermiers adversaires dans le jardin"""
        endpoint="garden/get-farmer-opponents"
        result=self.make_api_call(endpoint=endpoint, params=None, method='GET')

        if result and 'opponents' in result:
            return ['opponents']
        else : return []

    
    def get_leeks(self):
        """Récupère la liste des poireaux"""
        result = self.farmer_info
        if result and 'leeks' in result:
            leeks_dict = result['leeks']
            self.farmer_leeks = result['leeks'];
            return list(leeks_dict.values()) if isinstance(leeks_dict, dict) else leeks_dict
        return []
    
    def get_leek_name(self, leek_id):
        """Récupère les informations d'un poireau"""
        endpoint = f"leek/get/{leek_id}"
        result = self.make_api_call(endpoint=endpoint, params=None, method='GET')
        if result and 'name' in result:
            return result.get('name', '')
        return None

    def get_garden_leek_opponents(self, leek_id):
        """Récupère la liste des poireaux adversaires disponibles dans le jardin"""
        # L'API LeekWars attend l'ID directement dans l'URL comme paramètre de chemin
        endpoint = f"garden/get-leek-opponents/{leek_id}"
        result = self.make_api_call(endpoint, params=None, method='GET')
        
        if result and 'opponents' in result:
            return result['opponents']
        elif result and 'leeks' in result:  # Parfois la clé est différente
            return result['leeks']
        return []
    
    def debug_garden_access(self):
        """Test spécifique pour garden/get-leek-opponents"""
        leeks = self.get_leeks()
        if leeks:
            leek_id = leeks[0]['id']
            self.logger.info(f"Test garden/get-leek-opponents avec leek_id={leek_id}")
            
            # Test 1: Avec l'ID dans l'URL
            self.logger.info("Test 1: ID dans l'URL")
            response = self.session.get(
                f"{self.base_url}garden/get-leek-opponents/{leek_id}",
                cookies=self.cookies
            )
            self.logger.info(f"Status: {response.status_code} - {response.text[:100]}")
            
            # Test 2: Avec paramètres GET classiques
            self.logger.info("Test 2: Paramètres GET")
            response = self.session.get(
                f"{self.base_url}garden/get-leek-opponents",
                params={'leek_id': leek_id},
                cookies=self.cookies
            )
            self.logger.info(f"Status: {response.status_code} - {response.text[:100]}")
            
            # Test 3: Sans paramètres (au cas où)
            self.logger.info("Test 3: Sans paramètres")
            response = self.session.get(
                f"{self.base_url}garden/get-leek-opponents",
                cookies=self.cookies
            )
            self.logger.info(f"Status: {response.status_code} - {response.text[:100]}")

    def start_garden_fight(self, leek_id, target_id):
        """Lance un combat de jardin"""
        params = {leek_id, target_id}
        
        result = self.make_api_call("garden/start-solo-fight", {'leek_id': leek_id, 'target_id': target_id}, method='POST')
        
        if result:
            if 'fight' in result:
                fight_id = result['fight']
                self.logger.info(f"Combat lancé ! Fight ID: {fight_id}")
                return fight_id
            elif 'error' in result:
                self.logger.warning(f"Erreur combat: {result['error']}")
                # Erreurs spécifiques selon le forum
                if result['error'] == 'error_fight_target_not_in_garden':
                    self.logger.info("L'adversaire n'est plus disponible, recherche d'un autre...")
                elif result['error'] == 'wrong_token':
                    self.logger.warning("Token invalide, reconnexion nécessaire")
        
        return None
    
    def get_fight_result(self, fight_id):
        """Récupère le résultat d'un combat"""
        endpoint = f"fight/get/{fight_id}"
        result = self.make_api_call(endpoint=endpoint, params=None, method='GOT')
        if result and 'fight' in result:
            return result['fight']
        return result
    
    def wait_for_fight_end(self, fight_id, max_wait=300):
        """Attend la fin d'un combat"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            fight_info = self.get_fight_result(fight_id)
            
            if fight_info:
                status = fight_info.get('status', '')
                # Status peut être un string ou un int
                if status in ['finished', 'end', 2] or status == 2:
                    return fight_info
                elif status in ['running', 'progress', 1] or status == 1:
                    self.logger.debug(f"Combat {fight_id} en cours...")
                else:
                    self.logger.debug(f"Status combat: {status}")
            
            time.sleep(5)
        
        self.logger.warning(f"Timeout pour le combat {fight_id}")
        return None
    
    def auto_fight_session(self, duration_minutes=30, delay_between_fights=60):
        """Session de combats automatiques"""
        if not self.login():
            self.logger.error("Impossible de se connecter")
            return False
        
        # Test de l'API
        if not self.test_api_access():
            self.logger.error("Accès API non fonctionnel")
            return False
        
        # Récupérer les poireaux
        leeks = self.get_leeks()
        if not leeks:
            self.logger.error("Aucun poireau trouvé")
            return False
        
        self.logger.info(f"Poireaux disponibles:")
        for leek in leeks:
            name = leek.get('name', 'Inconnu')
            level = leek.get('level', '?')
            talent = leek.get('talent', '?')
            id = leek.get('id', '?')
            self.logger.info(f"   - {name} (Niv.{level}, Talent: {talent}), Id: #{id})")
        
        chosen_leek = int(input("Choose your fighter(leek_id): " ) or "34872")
        # # Sélectionner le meilleur poireau
        # best_leek = max(leeks, key=lambda l: l.get('level', 0))
        # leek_name = best_leek.get('name', 'Poireau')
        # leek_id = best_leek.get('id')
        
        # self.logger.info(f"Poireau sélectionné: {leek_name} (ID: {leek_id})")
        leek_id = chosen_leek

        leek_name = self.get_leek_name(chosen_leek)
        self.logger.info(f"Poireau sélectionné: {leek_name} (ID: {chosen_leek})")

        
        # Session de combats
        end_time = time.time() + (duration_minutes * 60)
        fight_count = 0
        victories = 0
        
        while time.time() < end_time:
            self.logger.info(f"Combat #{fight_count + 1}")
            
            # Optionnel: récupérer les adversaires disponibles
            opponents = self.get_garden_leek_opponents(leek_id)
            if opponents:
                self.logger.info(f"{len(opponents)} adversaires disponibles")
                # Choisir l'adversaire le plus faible
                weakest = min(opponents, key=lambda o: o.get('talent', 999999))
                target_id = weakest.get('id')
                target_name = weakest.get('name', 'Inconnu')
                self.logger.info(f"   Cible: {target_name} (Talent: {weakest.get('talent', '?')})")
                
                fight_id = self.start_garden_fight(leek_id, target_id)
            else:
                self.logger.info("Combat automatique (pas d'adversaires spécifiques)")
                fight_id = self.start_garden_fight(leek_id)
            
            if fight_id:
                # Attendre la fin
                fight_result = self.wait_for_fight_end(fight_id)
                
                if fight_result:
                    winner = fight_result.get('winner', 0)
                    if winner == 1:
                        victories += 1
                        self.logger.info("Victoire !")
                    else:
                        self.logger.info("Défaite...")
                    
                    fight_count += 1
                else:
                    self.logger.warning("Combat non terminé ou timeout")
            else:
                self.logger.warning("Impossible de lancer le combat")
                # Attendre un peu plus en cas d'erreur
                time.sleep(30)
            
            # Attendre avant le prochain combat
            if time.time() < end_time:
                self.logger.info(f"Attente {delay_between_fights}s...")
                time.sleep(delay_between_fights)
        
        # Statistiques finales
        self.logger.info(f"SESSION TERMINÉE !")
        self.logger.info(f"   Durée: {duration_minutes} minutes")
        self.logger.info(f"   Combats: {fight_count}")
        self.logger.info(f"   Victoires: {victories}")
        self.logger.info(f"   Défaites: {fight_count - victories}")
        if fight_count > 0:
            win_rate = (victories / fight_count) * 100
            self.logger.info(f"   Taux de victoire: {win_rate:.1f}%")
        
        return True

# Script principal
if __name__ == "__main__":
    print("BOT LEEKWARS")
    print("=" * 45)
    
    # Configuration
    # USERNAME = input("Nom d'utilisateur LeekWars: ")
    # PASSWORD = input("Mot de passe: ")
    USERNAME = "PCMT"
    PASSWORD = '80nP7T6Lq=lw'
    
    # Créer le bot
    bot = LeekWarsBot(USERNAME, PASSWORD)
    
    # Test complet
    if bot.login():
        print("\nConnexion réussie !")
        
        # Test API
        if bot.test_api_access():
            print("Accès API confirmé !")
            
            # Récupération des infos
            farmer = bot.get_farmer_info()
            if farmer:
                print(f"Fermier: {farmer.get('name')}")
                print(f"Talent: {farmer.get('talent', 0)}")
            
            leeks = bot.get_leeks()
            # print(f"Poireaux: {leeks}")
            if leeks:
                for leek in leeks:
                    print(leek.get('name'), leek.get('talent'))

            # bot.debug_garden_access()
            
            # Proposer la session automatique
            if leeks:
                print(f"\nTout est prêt pour les combats automatiques !")
                choice = input("Lancer une session ? (o/N): ")
                if choice.lower() in ['o', 'oui', 'y', 'yes']:
                    duration = int(input("Durée en minutes (défaut: 5): ") or "30")
                    delay = int(input("Délai entre combats en secondes (défaut: 15): ") or "60")
                    
                    bot.auto_fight_session(duration_minutes=duration, delay_between_fights=delay)
            
        else:
            print("Accès API non fonctionnel")
            print("Vérifiez vos droits d'accès à l'API LeekWars")
        
    else:
        print("Échec de la connexion")
        print("Vérifiez vos identifiants LeekWars")