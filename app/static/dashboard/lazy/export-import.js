// Export/Import functions
async function exportData() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/export/`);
    if (!response.ok) {
      throw new Error('Export failed');
    }

    const data = await response.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `omnitrackr-export-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    alert(`Export successful! Exported ${data.export_metadata.total_movies} movies, ${data.export_metadata.total_tv_shows} TV shows, ${data.export_metadata.total_anime || 0} anime, ${data.export_metadata.total_video_games || 0} video games, ${data.export_metadata.total_music || 0} music, ${data.export_metadata.total_books || 0} books, ${data.export_metadata.total_manga || 0} manga, ${data.export_metadata.total_podcasts || 0} podcasts, ${data.export_metadata.total_custom_tabs || 0} custom tabs, ${data.export_metadata.total_activities || 0} journal entries, and ${data.export_metadata.total_progress_checkpoints || 0} private progress checkpoints.`);
  } catch (error) {
    alert('Export failed: ' + error.message);
  }
}

// Spreadsheet, Letterboxd and Goodreads files from the export panel in Account Settings.
async function downloadLibraryExport(button) {
  const format = button?.dataset.exportFormat;
  const status = document.getElementById('exportStudioStatus');
  if (!format) return;
  if (format === 'json') {
    await exportData();
    return;
  }
  const label = button.textContent;
  button.disabled = true;
  button.textContent = 'Preparing…';
  if (status) status.textContent = '';
  try {
    const response = await authenticatedFetch(`${API_BASE}/export/${encodeURIComponent(format)}/`);
    if (!response.ok) {
      throw new Error(response.status === 429 ? 'Too many downloads in the last hour. Try again later.' : 'The export could not be prepared.');
    }
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = match ? match[1] : `omnitrackr-${format}.${format === 'spreadsheet' ? 'zip' : 'csv'}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    if (status) status.textContent = `Downloaded ${link.download}.`;
  } catch (error) {
    if (status) status.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

async function importData(fileInput) {
  const file = fileInput.files[0];
  if (!file) return;

  if (!file.name.endsWith('.json')) {
    alert('Please select a JSON file.');
    return;
  }

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await authenticatedFetch(`${API_BASE}/import/file/`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Import failed');
    }

    const result = await response.json();
    let message = `Import completed!\n`;
    message += `Movies: ${result.movies_created} created, ${result.movies_updated} updated\n`;
    message += `TV Shows: ${result.tv_shows_created} created, ${result.tv_shows_updated} updated\n`;
    message += `Anime: ${result.anime_created || 0} created, ${result.anime_updated || 0} updated\n`;
    message += `Video Games: ${result.video_games_created || 0} created, ${result.video_games_updated || 0} updated\n`;
    message += `Music: ${result.music_created || 0} created, ${result.music_updated || 0} updated\n`;
    message += `Books: ${result.books_created || 0} created, ${result.books_updated || 0} updated\n`;
    message += `Manga: ${result.manga_created || 0} created, ${result.manga_updated || 0} updated\n`;
    message += `Podcasts: ${result.podcasts_created || 0} created, ${result.podcasts_updated || 0} updated\n`;
    message += `Custom Tabs: ${result.custom_tabs_created || 0} created, ${result.custom_tabs_updated || 0} updated`;
    message += `\nPrivate progress: ${result.progress_created || 0} restored, ${result.progress_skipped || 0} skipped. Existing or cleared checkpoints stay unchanged.`;

    if (result.errors.length > 0) {
      message += `\n\nErrors:\n${result.errors.join('\n')}`;
    }

    alert(message);

    // Refresh the current tab
    if (currentTab === 'movies') {
      loadMovies();
    } else if (currentTab === 'tv-shows') {
      loadTVShows();
    } else if (currentTab === 'anime') {
      loadAnime();
    } else if (currentTab === 'video-games') {
      loadVideoGames();
    } else if (currentTab === 'music') {
      loadMusic();
    } else if (currentTab === 'books') {
      loadBooks();
    } else if (currentTab === 'manga') {
      loadManga();
    } else if (currentTab === 'podcasts') {
      loadPodcasts();
    } else if (currentTab && currentTab.startsWith('custom-')) {
      const tabId = parseInt(currentTab.replace('custom-', ''));
      const tab = customTabs.find(t => t.id === tabId);
      if (tab) {
        loadCustomTabItems(tab);
      }
    }
    
    if ((result.custom_tabs_created || 0) > 0 || (result.custom_tabs_updated || 0) > 0) {
      loadCustomTabs();
    }

    // Clear the file input
    fileInput.value = '';
  } catch (error) {
    alert('Import failed: ' + error.message);
    fileInput.value = '';
  }
}

