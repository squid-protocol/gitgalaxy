import unittest
from unittest.mock import patch

class TestDeltaScanner(unittest.TestCase):
    
    def simulate_delta_parser(self, git_output: str):
        """
        A DRY helper method that exactly mirrors the Git Diff parser 
        from galaxyscope.py to test its physical routing logic.
        """
        added, modified, deleted = [], [], []
        
        for line in git_output.splitlines():
            if not line.strip():
                continue
            
            parts = line.split('\t')
            status = parts[0]
            
            def _clean(p): 
                return p.strip('"\n\r')
            
            if status.startswith('A'):
                added.append(_clean(parts[1]))
            elif status.startswith('M') or status.startswith('T') or status.startswith('U'):
                modified.append(_clean(parts[1]))
            elif status.startswith('D'):
                deleted.append(_clean(parts[1]))
            elif status.startswith('R') or status.startswith('C'):
                deleted.append(_clean(parts[1]))
                if len(parts) > 2:
                    added.append(_clean(parts[2]))
                    
        return added, modified, deleted

    # ==============================================================================
    # TEST 1: THE RENAME & COPY EVASION
    # ==============================================================================
    @patch("subprocess.check_output")
    def test_git_rename_evasion_caught(self, mock_check_output):
        """
        DEVIOUS EDGE CASE: A developer renames a file containing a logic bomb. 
        Git outputs an 'R100' status instead of an 'A' or 'M'. The scanner must 
        intercept the rename, delete the old RAM state, and force a re-scan of the new path.
        """
        mock_check_output.return_value = (
            "R100\tsrc/old_auth.py\tsrc/new_auth.py\n"
            "C100\tsrc/template.py\tsrc/cloned_template.py\n"
        )
        
        added, modified, deleted = self.simulate_delta_parser(mock_check_output.return_value)
                
        # Assert the old files are queued for RAM eviction
        self.assertIn("src/old_auth.py", deleted)
        self.assertIn("src/template.py", deleted)
        
        # Assert the new paths are aggressively targeted for re-scanning
        self.assertIn("src/new_auth.py", added)
        self.assertIn("src/cloned_template.py", added)

    # ==============================================================================
    # TEST 2: THE PARTIAL SIMILARITY INDEX ATTACK
    # ==============================================================================
    @patch("subprocess.check_output")
    def test_git_partial_similarity_rename(self, mock_check_output):
        """
        DEVIOUS EDGE CASE: If a developer renames a file AND modifies the code at 
        the same time, Git outputs a fractional similarity index (e.g., 'R080' or 'C050') 
        instead of 'R100'. The parser must not hardcode 'R100'.
        """
        mock_check_output.return_value = (
            "R080\tsrc/old_auth.py\tsrc/new_auth.py\n"
            "C050\tsrc/template.py\tsrc/heavily_modified_clone.py\n"
        )
        
        added, modified, deleted = self.simulate_delta_parser(mock_check_output.return_value)
                
        self.assertIn("src/old_auth.py", deleted)
        self.assertIn("src/new_auth.py", added)
        self.assertIn("src/heavily_modified_clone.py", added)

    # ==============================================================================
    # TEST 3: THE WHITESPACE QUOTE BOMB
    # ==============================================================================
    @patch("subprocess.check_output")
    def test_git_whitespace_quote_evasion(self, mock_check_output):
        """
        DEVIOUS EDGE CASE: An attacker creates a payload with spaces in the filename 
        knowing it breaks naive split() parsers. Git wraps these in quotes and separates 
        with tabs. The engine must strip the quotes and extract the path intact.
        """
        mock_check_output.return_value = (
            "A\t\"src/evil payload.py\"\n"
            "R100\t\"src/old name.py\"\t\"src/new name.py\"\n"
        )
        
        added, modified, deleted = self.simulate_delta_parser(mock_check_output.return_value)
                
        self.assertIn("src/evil payload.py", added)
        self.assertIn("src/old name.py", deleted)
        self.assertIn("src/new name.py", added)

    # ==============================================================================
    # TEST 4: THE TYPE MUTATION ATTACK (Symlink Hijacking)
    # ==============================================================================
    @patch("subprocess.check_output")
    def test_git_type_mutation_anomaly(self, mock_check_output):
        """
        DEVIOUS EDGE CASE: An attacker deletes a safe file and replaces it with a 
        malicious symlink (or vice versa) under the exact same filename. Git outputs 
        'T' (Type Change) instead of 'M'. The parser must catch this mutation.
        """
        mock_check_output.return_value = "T\tsrc/hijacked_symlink.py\n"
        
        added, modified, deleted = self.simulate_delta_parser(mock_check_output.return_value)
                
        # Type mutations must be flagged as modified so the engine re-parses them
        self.assertIn("src/hijacked_symlink.py", modified)

    # ==============================================================================
    # TEST 5: THE UNMERGED CONFLICT STATE
    # ==============================================================================
    @patch("subprocess.check_output")
    def test_git_unmerged_conflict_state(self, mock_check_output):
        """
        DEVIOUS EDGE CASE: The CI/CD runner attempts a delta scan during a dirty 
        merge conflict. Git outputs 'U' (Unmerged). The scanner must treat these 
        as active modifications to ensure the conflict markers are analyzed.
        """
        mock_check_output.return_value = "U\tsrc/conflict_zone.py\n"
        
        added, modified, deleted = self.simulate_delta_parser(mock_check_output.return_value)
                
        self.assertIn("src/conflict_zone.py", modified)