<script>
  // Vous pouvez ajouter des propriétés (props) si vous voulez contrôler
  // la quantité de texte, les balises HTML, etc.
  export let paragraphs = 1;

  let loremText = `
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim
    veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex
    ea commodo consequat. Duis aute irure dolor in reprehenderit in
    voluptate velit esse cillum dolore eu fugiat nulla pariatur.
    Excepteur sint occaecat cupidatat non proident, sunt in culpa qui
    officia deserunt mollit anim id est laborum.
  `;

  let fullLoremText = '';
  for (let i = 0; i < paragraphs; i++) {
    fullLoremText += `<p>${loremText.trim()}</p>`;
  }
</script>

<div class="lorem-ipsum-container">
  {@html fullLoremText}
</div>

<style>
  .lorem-ipsum-container {
    font-family: sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f9f9f9;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  /* Style pour les paragraphes générés */
  .lorem-ipsum-container p {
    margin-bottom: 1em; /* Espace entre les paragraphes */
  }

  .lorem-ipsum-container p:last-child {
    margin-bottom: 0; /* Pas de marge sous le dernier paragraphe */
  }
</style>